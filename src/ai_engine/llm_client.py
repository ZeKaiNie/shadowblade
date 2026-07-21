"""
LLM 客户端 - 统一封装本地 vLLM 与云端 API 的调用

白话讲解：
- 项目早期只用本地 vLLM（Qwen3-4B），现在加上云端选项后需要一个统一入口
- 云端选项：MiMo（小米百万亿激励计划，免费 7 亿 token）、DeepSeek（备用）
- 三者都用 OpenAI 兼容协议，主要差异在：
  1. API base URL 不同
  2. 本地不需要 API key，云端需要 Bearer token
  3. 模型名不同（vllm 用本地路径，云端用 mimo-v2.5-pro / deepseek-chat）
- API key 一律从环境变量读，**不写到 yaml 里被 commit**
"""
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml

try:
    import httpx
except ModuleNotFoundError:  # mock provider 离线运行时不需要 HTTP 依赖
    httpx = None

# 项目根目录（用于解析默认 settings.yaml 路径）
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
_DEFAULT_SETTINGS_PATH = _PROJECT_ROOT / "config" / "settings.yaml"


@dataclass
class LLMConfig:
    """
    运行时 LLM 配置（从 settings.yaml + 环境变量解析后的最终结果）

    白话讲解：
    yaml 里的 provider 字段决定走哪条路径，这个 dataclass 是解析后的统一形式
    业务代码只跟这个对象打交道，不关心配置来源是 yaml 还是环境变量
    """
    provider: str = "vllm"                                # vllm / mimo / deepseek / mock
    api_base: str = "http://127.0.0.1:8000/v1"            # OpenAI 兼容端点
    api_key: str = ""                                      # 本地为空字符串
    model: str = "models/qwen3-4b-awq"                    # 模型名/路径
    max_tokens: int = 2048
    temperature: float = 0.3
    timeout: float = 60.0
    extra_headers: dict = field(default_factory=dict)     # 网关额外头（保留扩展位）

    def is_local(self) -> bool:
        """是否为本地推理（不需要 API key、不会消耗云端配额）"""
        return self.provider == "vllm"

    def describe(self) -> str:
        """简短描述（用于日志、调试输出，避免泄露 api_key）"""
        masked = (
            "(local)"
            if not self.api_key
            else f"key=***{self.api_key[-4:] if len(self.api_key) >= 4 else '***'}"
        )
        return f"{self.provider}@{self.api_base} model={self.model} {masked}"


def _read_yaml(settings_path: Path) -> dict:
    """读取 yaml 配置（独立出来便于测试 mock）"""
    if not settings_path.exists():
        return {}
    with open(settings_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_llm_config(
    provider: Optional[str] = None,
    settings_path: Optional[Path] = None,
) -> LLMConfig:
    """
    从 settings.yaml + 环境变量加载 LLM 配置

    白话讲解：
    - `provider` 参数显式指定时优先（用于测试或运行时覆盖）
    - 否则从 yaml 的 `llm.provider` 字段读
    - 云端 provider 的 api_key 通过 `api_key_env` 字段指定的环境变量读取
      例如配置 `api_key_env: MIMO_API_KEY`，运行时去读 `os.getenv("MIMO_API_KEY")`

    参数:
        provider: 显式指定 provider（可选）
        settings_path: 自定义配置路径（测试用）

    返回:
        LLMConfig 对象（可直接传给 call_llm 使用）
    """
    if settings_path is None:
        settings_path = _DEFAULT_SETTINGS_PATH

    config = _read_yaml(settings_path)
    llm_cfg = config.get("llm", {})

    # 决定 provider：显式参数 > yaml.llm.provider > 默认 vllm
    provider = provider or llm_cfg.get("provider", "vllm")

    # 通用字段（所有 provider 共享）
    common = dict(
        max_tokens=int(llm_cfg.get("max_tokens", 2048)),
        temperature=float(llm_cfg.get("temperature", 0.3)),
        timeout=float(llm_cfg.get("timeout_seconds", 60.0)),
    )

    if provider == "vllm":
        # 本地 vLLM：优先读 llm.vllm 子节，否则回退到旧字段（向后兼容）
        sub = llm_cfg.get("vllm", {}) or {}
        api_base = sub.get("api_base") or llm_cfg.get("vllm_api_base", "http://127.0.0.1:8000/v1")
        model = sub.get("model_path") or llm_cfg.get("model_path", "models/qwen3-4b-awq")
        return LLMConfig(
            provider="vllm",
            api_base=api_base,
            api_key="",                # 本地 vLLM 不需要 key
            model=model,
            **common,
        )

    if provider in ("mimo", "deepseek"):
        sub = llm_cfg.get(provider, {}) or {}
        api_key_env = sub.get("api_key_env", "")
        # 优先环境变量，没有则尝试 yaml 里的 api_key（不推荐，但为了灵活性保留）
        api_key = os.getenv(api_key_env, "") if api_key_env else ""
        if not api_key:
            api_key = sub.get("api_key", "") or ""
        return LLMConfig(
            provider=provider,
            api_base=sub.get("api_base", ""),
            api_key=api_key,
            model=sub.get("model", ""),
            extra_headers=sub.get("extra_headers", {}) or {},
            **common,
        )

    if provider == "mock":
        # mock 只用于离线 harness 和单测，不读取 API key，也不访问网络。
        return LLMConfig(
            provider="mock",
            api_base="",
            api_key="",
            model="deterministic-instruction-following-mock",
            **common,
        )

    raise ValueError(f"不支持的 LLM provider: {provider}（仅支持 vllm / mimo / deepseek / mock）")


def call_llm(
    prompt: str,
    config: LLMConfig,
    system_prompt: Optional[str] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
) -> str:
    """
    通用 LLM 调用（OpenAI 兼容协议）

    白话讲解：
    vLLM、MiMo、DeepSeek 都遵守 OpenAI Chat Completion 接口规范，
    所以同一段代码能跑三家。差异只在 url、model 名、是否需要 Bearer 认证。

    参数:
        prompt: 用户消息内容
        config: 由 load_llm_config 解析得到
        system_prompt: 系统消息（不传则用默认审计员人设）
        temperature/max_tokens: 临时覆盖配置（不传则用 config 的值）

    返回:
        LLM 文本回复（content 字段）

    异常:
        httpx.ConnectError - 端点不可达（本地 vLLM 没启动 / 云端网络断）
        httpx.HTTPStatusError - HTTP 错误（401 鉴权、429 限流等）
    """
    if config.provider == "mock":
        # 结构化 cross-app mock 在 src.crossapp.llm 中实现；这里保留 provider
        # 分支，使统一配置入口能识别 mock，同时避免误把 mock 当成联网调用。
        return (
            "MOCK_PROVIDER_CONFIGURED: use "
            "src.crossapp.llm.MockInstructionFollowingLLM for structured decisions."
        )

    if httpx is None:
        raise RuntimeError("调用联网 LLM 需要安装 httpx；mock provider 不需要该依赖")

    if system_prompt is None:
        system_prompt = "你是一个专业的 AI Agent 安全审计分析师。请用中文回答。"

    # 构造请求头：本地不需要 Bearer，云端必须
    headers = {"Content-Type": "application/json"}
    if config.api_key:
        headers["Authorization"] = f"Bearer {config.api_key}"
    if config.extra_headers:
        headers.update(config.extra_headers)

    # 请求体：标准 OpenAI Chat Completion 格式
    payload = {
        "model": config.model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        "temperature": temperature if temperature is not None else config.temperature,
        "max_tokens": max_tokens if max_tokens is not None else config.max_tokens,
    }

    response = httpx.post(
        f"{config.api_base.rstrip('/')}/chat/completions",
        json=payload,
        headers=headers,
        timeout=config.timeout,
    )
    response.raise_for_status()
    data = response.json()
    return data["choices"][0]["message"]["content"]
