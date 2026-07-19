"""
一致性核验模块测试（纯单元测试，不依赖 Docker/数据集）
"""
from src.conformance import (
    Capability,
    declared_from_skill_md,
    normalize_declared,
    observed_from_audit,
    observed_from_events,
    parse_allowed_tools,
    verify_conformance,
)
from src.dynamic_engine.models import (
    BehaviorEvent,
    BehaviorType,
    DynamicAuditResult,
    DynamicFinding,
)


class TestNormalizeDeclared:
    def test_network_variants(self):
        assert Capability.NETWORK in normalize_declared(["network access"])
        assert Capability.NETWORK in normalize_declared(["requires HTTPS"])
        assert Capability.NETWORK in normalize_declared(["network_access"])

    def test_credential(self):
        caps = normalize_declared(["needs API key", "token"])
        assert Capability.CREDENTIAL_ACCESS in caps

    def test_identity_write(self):
        assert Capability.IDENTITY_WRITE in normalize_declared(["edits SOUL.md"])

    def test_empty(self):
        assert normalize_declared([]) == set()

    def test_unmatched_string_ignored(self):
        assert normalize_declared(["just prints hello"]) == set()


class TestAllowedTools:
    def test_parse_allowed_tools(self):
        md = (
            "---\n"
            "name: x\n"
            "allowed-tools: Read, WebFetch, WebSearch, Grep, Bash(diff:*), Bash(grep:*)\n"
            "---\n# x\n"
        )
        caps = parse_allowed_tools(md)
        assert Capability.NETWORK in caps       # WebFetch/WebSearch
        assert Capability.SUBPROCESS in caps    # Bash(...)
        assert Capability.FILE_READ in caps     # Read/Grep

    def test_no_allowed_tools(self):
        assert parse_allowed_tools("# just a title\n") == set()

    def test_declared_from_skill_md_union(self):
        md = (
            "---\nname: x\nallowed-tools: Bash(ls:*)\n---\n"
            "# x\nThis skill requires network access.\n"
        )
        caps = declared_from_skill_md(md, ["network access"])
        assert Capability.SUBPROCESS in caps    # 来自 allowed-tools
        assert Capability.NETWORK in caps       # 来自正文关键词


class TestObserved:
    def test_from_events(self):
        events = [
            BehaviorEvent(behavior=BehaviorType.NETWORK, event="socket.connect"),
            BehaviorEvent(behavior=BehaviorType.OTHER, event="misc"),
        ]
        assert observed_from_events(events) == {Capability.NETWORK}

    def test_from_audit_aggregates(self):
        result = DynamicAuditResult(
            executed=True,
            network_targets=["1.2.3.4:443"],
            subprocess_calls=["sh -c id"],
            identity_files_written=["SOUL.md"],
            honeypot_triggered=True,
        )
        caps = observed_from_audit(result)
        assert caps == {
            Capability.NETWORK,
            Capability.SUBPROCESS,
            Capability.IDENTITY_WRITE,
            Capability.CREDENTIAL_ACCESS,
        }

    def test_credential_read_maps_to_credential_access(self):
        """仅读取敏感凭据/诱饵文件（未外传）也应映射为 credential_access 观测能力。"""
        result = DynamicAuditResult(
            executed=True,
            credential_read_paths=["/work/.aws/credentials"],
        )
        assert Capability.CREDENTIAL_ACCESS in observed_from_audit(result)

    def test_from_audit_findings_behavior(self):
        result = DynamicAuditResult(
            executed=True,
            findings=[
                DynamicFinding(
                    severity="high", message="wrote file",
                    behavior=BehaviorType.FILE_WRITE,
                )
            ],
        )
        assert Capability.FILE_WRITE in observed_from_audit(result)


class TestVerifyConformance:
    def test_benign_conformant(self):
        # 声明联网，实际只联网 → 无偏差，放行
        result = DynamicAuditResult(executed=True, network_targets=["api.x:443"])
        c = verify_conformance(["network access"], result)
        assert c.undeclared == []
        assert c.decision == "allow"

    def test_undeclared_network_review(self):
        # 未声明任何东西，却联网 → 未声明敏感能力，进复核
        result = DynamicAuditResult(executed=True, network_targets=["evil:443"])
        c = verify_conformance([], result)
        assert "network" in c.undeclared_sensitive
        assert c.decision in ("review", "deny")

    def test_honeypot_forces_deny(self):
        # 蜜罐命中 = 确凿凭据窃取 → 一律阻断
        result = DynamicAuditResult(
            executed=True,
            honeypot_triggered=True,
            network_targets=["exfil.evil:443"],
        )
        c = verify_conformance(["network access"], result)
        assert c.honeypot_triggered is True
        assert c.decision == "deny"
        assert c.deviation_score >= 0.6

    def test_declared_network_but_suspicious_target_flagged(self):
        # 如实声明了网络权限，但外联到已知恶意/外传目标 → 不该被"已声明"洗白，至少 review
        result = DynamicAuditResult(
            executed=True,
            network_targets=["webhook.site/abc:443"],
            suspicious_network_targets=["webhook.site/abc:443"],
        )
        c = verify_conformance(["network access"], result)
        assert c.undeclared == []  # 网络已声明，无未声明能力
        assert c.suspicious_targets == ["webhook.site/abc:443"]
        assert c.decision in ("review", "deny")

    def test_undeclared_network_plus_suspicious_target_deny(self):
        # 未声明网络 + 外联可疑目标 → 叠加升级为 deny
        result = DynamicAuditResult(
            executed=True,
            network_targets=["api.telegram.org/bot:443"],
            suspicious_network_targets=["api.telegram.org/bot:443"],
        )
        c = verify_conformance([], result)
        assert c.decision == "deny"

    def test_identity_write_high_risk(self):
        # 未声明的身份文件篡改（控制面攻击）→ 高偏差
        result = DynamicAuditResult(
            executed=True, identity_files_written=["AGENTS.md"]
        )
        c = verify_conformance([], result)
        assert "identity_write" in c.undeclared_sensitive
        assert c.deviation_score >= 0.5

    def test_unused_declared_is_harmless(self):
        # 声明了联网但没用 → unused，不算偏差，放行
        result = DynamicAuditResult(executed=True)
        c = verify_conformance(["network access"], result)
        assert "network" in c.unused
        assert c.decision == "allow"
