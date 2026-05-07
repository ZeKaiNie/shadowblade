"""
LLM 客户端测试 - 验证云端 API 切换的配置加载、调用、向后兼容

白话讲解：
- 单元测试：用临时 yaml 文件 + monkeypatch 环境变量，验证配置解析正确
- 集成测试：需要 MIMO_API_KEY 才会跑（默认 skip，避免本地测试消耗云端配额）
"""
import os
import textwrap
from pathlib import Path

import pytest

from src.ai_engine.llm_client import (
    LLMConfig,
    load_llm_config,
    call_llm,
)


# ---------- 单元测试：配置加载（不需要网络） ----------

class TestLoadLLMConfig:
    """验证 load_llm_config 正确解析 settings.yaml + 环境变量"""

    def _write_yaml(self, tmp_path: Path, content: str) -> Path:
        """工具函数：写入临时 yaml"""
        p = tmp_path / "settings.yaml"
        p.write_text(textwrap.dedent(content), encoding="utf-8")
        return p

    def test_default_provider_is_vllm(self, tmp_path):
        """没有显式 provider 字段时默认走本地 vLLM"""
        path = self._write_yaml(tmp_path, """
            llm:
              max_tokens: 1000
              temperature: 0.5
              vllm:
                api_base: "http://127.0.0.1:8000/v1"
                model_path: "models/qwen3-4b-awq"
        """)
        cfg = load_llm_config(settings_path=path)
        assert cfg.provider == "vllm"
        assert cfg.api_base == "http://127.0.0.1:8000/v1"
        assert cfg.model == "models/qwen3-4b-awq"
        assert cfg.api_key == ""           # 本地不需要 key
        assert cfg.is_local() is True
        assert cfg.max_tokens == 1000
        assert cfg.temperature == 0.5

    def test_explicit_provider_override(self, tmp_path, monkeypatch):
        """provider 参数显式指定时覆盖 yaml 配置"""
        monkeypatch.setenv("MIMO_API_KEY", "tp-test-key-12345")
        path = self._write_yaml(tmp_path, """
            llm:
              provider: "vllm"
              mimo:
                api_base: "https://token-plan-cn.xiaomimimo.com/v1"
                model: "mimo-v2.5-pro"
                api_key_env: "MIMO_API_KEY"
        """)
        # yaml 里 provider 是 vllm，但显式指定 mimo
        cfg = load_llm_config(provider="mimo", settings_path=path)
        assert cfg.provider == "mimo"
        assert cfg.model == "mimo-v2.5-pro"
        assert cfg.api_key == "tp-test-key-12345"
        assert cfg.is_local() is False

    def test_mimo_reads_api_key_from_env(self, tmp_path, monkeypatch):
        """MiMo provider 应从 api_key_env 指定的环境变量读取 key"""
        monkeypatch.setenv("MIMO_API_KEY", "tp-real-key")
        path = self._write_yaml(tmp_path, """
            llm:
              provider: "mimo"
              mimo:
                api_base: "https://token-plan-cn.xiaomimimo.com/v1"
                model: "mimo-v2.5-pro"
                api_key_env: "MIMO_API_KEY"
        """)
        cfg = load_llm_config(settings_path=path)
        assert cfg.api_key == "tp-real-key"

    def test_mimo_missing_env_key_returns_empty(self, tmp_path, monkeypatch):
        """环境变量未设置时 api_key 应为空字符串（调用时会失败，但配置加载不应崩）"""
        monkeypatch.delenv("MIMO_API_KEY", raising=False)
        path = self._write_yaml(tmp_path, """
            llm:
              provider: "mimo"
              mimo:
                api_base: "https://token-plan-cn.xiaomimimo.com/v1"
                model: "mimo-v2.5-pro"
                api_key_env: "MIMO_API_KEY"
        """)
        cfg = load_llm_config(settings_path=path)
        assert cfg.api_key == ""

    def test_deepseek_provider(self, tmp_path, monkeypatch):
        """DeepSeek provider 同样能正确解析"""
        monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-deepseek-test")
        path = self._write_yaml(tmp_path, """
            llm:
              provider: "deepseek"
              deepseek:
                api_base: "https://api.deepseek.com/v1"
                model: "deepseek-chat"
                api_key_env: "DEEPSEEK_API_KEY"
        """)
        cfg = load_llm_config(settings_path=path)
        assert cfg.provider == "deepseek"
        assert cfg.api_base == "https://api.deepseek.com/v1"
        assert cfg.api_key == "sk-deepseek-test"

    def test_invalid_provider_raises(self, tmp_path):
        """不支持的 provider 应抛 ValueError"""
        path = self._write_yaml(tmp_path, """
            llm:
              provider: "claude"
        """)
        with pytest.raises(ValueError, match="不支持的 LLM provider"):
            load_llm_config(settings_path=path)

    def test_legacy_field_fallback(self, tmp_path):
        """缺少 llm.vllm 子节时回退到旧的 vllm_api_base / model_path（向后兼容）"""
        path = self._write_yaml(tmp_path, """
            llm:
              vllm_api_base: "http://127.0.0.1:8000/v1"
              model_path: "models/qwen3-4b-awq"
        """)
        cfg = load_llm_config(settings_path=path)
        assert cfg.provider == "vllm"
        assert cfg.api_base == "http://127.0.0.1:8000/v1"
        assert cfg.model == "models/qwen3-4b-awq"

    def test_describe_masks_api_key(self, tmp_path, monkeypatch):
        """describe() 应该脱敏 api_key（避免日志泄露）"""
        monkeypatch.setenv("MIMO_API_KEY", "tp-secret-key-very-long-12345")
        path = self._write_yaml(tmp_path, """
            llm:
              provider: "mimo"
              mimo:
                api_base: "https://token-plan-cn.xiaomimimo.com/v1"
                model: "mimo-v2.5-pro"
                api_key_env: "MIMO_API_KEY"
        """)
        cfg = load_llm_config(settings_path=path)
        desc = cfg.describe()
        # 完整 key 不应出现在描述里，只露最后 4 位
        assert "tp-secret-key-very-long" not in desc
        assert "2345" in desc           # 只有最后 4 位

    def test_default_settings_loadable(self):
        """项目默认 settings.yaml 应能被加载（不抛错）"""
        # 白话讲解：这个测试保护 settings.yaml 不被改坏
        cfg = load_llm_config()
        assert cfg.provider in ("vllm", "mimo", "deepseek")
        assert cfg.api_base != ""
        assert cfg.model != ""


# ---------- 单元测试：call_llm 请求构造 ----------

class TestCallLLMRequestBuilding:
    """验证 call_llm 在不同 provider 下的 HTTP 请求构造正确（用 monkeypatch 拦截）"""

    def test_local_vllm_no_auth_header(self, monkeypatch):
        """本地 vLLM 不应发送 Authorization 头"""
        captured = {}

        class MockResponse:
            status_code = 200
            def raise_for_status(self): pass
            def json(self):
                return {"choices": [{"message": {"content": "ok"}}]}

        def mock_post(url, json=None, headers=None, timeout=None):
            captured["url"] = url
            captured["headers"] = headers
            captured["json"] = json
            return MockResponse()

        monkeypatch.setattr("httpx.post", mock_post)
        cfg = LLMConfig(
            provider="vllm",
            api_base="http://127.0.0.1:8000/v1",
            api_key="",
            model="models/qwen3-4b-awq",
        )
        result = call_llm("hello", cfg)
        assert result == "ok"
        assert "Authorization" not in captured["headers"]   # 本地不带 Bearer
        assert captured["json"]["model"] == "models/qwen3-4b-awq"

    def test_cloud_provider_adds_bearer(self, monkeypatch):
        """云端调用应自动加 Bearer 认证头"""
        captured = {}

        class MockResponse:
            status_code = 200
            def raise_for_status(self): pass
            def json(self):
                return {"choices": [{"message": {"content": "cloud reply"}}]}

        def mock_post(url, json=None, headers=None, timeout=None):
            captured["headers"] = headers
            return MockResponse()

        monkeypatch.setattr("httpx.post", mock_post)
        cfg = LLMConfig(
            provider="mimo",
            api_base="https://token-plan-cn.xiaomimimo.com/v1",
            api_key="tp-test-key",
            model="mimo-v2.5-pro",
        )
        result = call_llm("hello", cfg)
        assert result == "cloud reply"
        assert captured["headers"]["Authorization"] == "Bearer tp-test-key"

    def test_url_trailing_slash_handled(self, monkeypatch):
        """api_base 末尾有/无斜杠都应正确拼接"""
        captured = {}

        class MockResponse:
            status_code = 200
            def raise_for_status(self): pass
            def json(self):
                return {"choices": [{"message": {"content": "ok"}}]}

        def mock_post(url, json=None, headers=None, timeout=None):
            captured["url"] = url
            return MockResponse()

        monkeypatch.setattr("httpx.post", mock_post)
        cfg = LLMConfig(
            provider="mimo",
            api_base="https://token-plan-cn.xiaomimimo.com/v1/",   # 故意带斜杠
            api_key="tp-key",
            model="mimo-v2.5-pro",
        )
        call_llm("hi", cfg)
        # 不应出现 //chat/completions 这种双斜杠
        assert captured["url"] == "https://token-plan-cn.xiaomimimo.com/v1/chat/completions"


# ---------- 集成测试：真实云端调用（需要 MIMO_API_KEY） ----------

def has_mimo_key() -> bool:
    """检查是否设置了 MIMO_API_KEY 环境变量"""
    key = os.getenv("MIMO_API_KEY", "")
    return bool(key) and key.startswith(("tp-", "sk-"))


@pytest.mark.skipif(not has_mimo_key(), reason="未设置 MIMO_API_KEY 环境变量，跳过云端集成测试")
class TestMiMoIntegration:
    """真实调用 MiMo 云端 API（消耗 token，仅在 CI 或手动验证时跑）"""

    def test_mimo_chat_completion(self):
        """端到端：用真实 MiMo API 完成一次对话"""
        cfg = load_llm_config(provider="mimo")
        assert cfg.api_key, "MIMO_API_KEY 应该已加载"
        result = call_llm("请用一个字回答：1+1=", cfg)
        assert isinstance(result, str)
        assert len(result) > 0
