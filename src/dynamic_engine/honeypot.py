"""
动态审计引擎 - 蜜罐（Honeypot）诱饵

白话讲解：
- 蜜罐 = 故意放的"假宝贝"。我们在沙箱里放上假的 API Key、假的 SSH 私钥、
  假的 .env 凭据文件。这些假凭据里都埋了一段**独一无二的随机标记**。
- 正常技能根本不会去碰这些敏感文件；只有窃密型恶意技能才会去读它们、
  再想办法把内容发出去。
- 一旦我们在"网络请求 / 子进程命令行"里发现了那段随机标记，就等于人赃并获——
  证明这个技能确实在窃取并外传凭据（ClawHavoc 的核心攻击手法）。
- 这就是"主动诱捕"，比被动地猜"它是不是恶意"要硬核得多。
"""
from __future__ import annotations

import json
import secrets
from dataclasses import dataclass, field
from pathlib import Path

# 默认蜜罐环境变量名（值会在运行时填入带随机标记的假凭据）
DEFAULT_ENV_KEYS = [
    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "AWS_SECRET_ACCESS_KEY",
    "OPENCLAW_API_KEY",
]

# 默认蜜罐假文件（相对沙箱工作区的路径 → 文件用途）
# 白话讲解：这些路径对应 ClawHavoc 真实窃取目标（SSH 密钥、.env、ClawHub 凭据）
DEFAULT_FAKE_FILES = {
    ".ssh/id_rsa": "ssh_private_key",
    ".env": "dotenv_credentials",
    ".clawdbot/.env": "clawhub_credentials",
    ".config/openclaw/credentials.json": "openclaw_oauth",
}


@dataclass
class Honeypot:
    """
    一份蜜罐配置 + 它埋下的所有标记

    白话讲解：
    - env_vars: 要注入沙箱的假环境变量（含随机标记）
    - files: 要写进沙箱工作区的假文件（相对路径 → 内容）
    - markers: 所有随机标记的集合。监控时只要在行为参数里发现任一标记，
      就判定"蜜罐被触发"（凭据外传）
    """
    env_vars: dict[str, str] = field(default_factory=dict)
    files: dict[str, str] = field(default_factory=dict)
    markers: list[str] = field(default_factory=list)

    def to_json(self) -> str:
        """序列化为 JSON，交给沙箱里的 harness 读取并布置现场"""
        return json.dumps(
            {"env_vars": self.env_vars, "files": self.files, "markers": self.markers},
            ensure_ascii=False,
        )

    @classmethod
    def from_json(cls, text: str) -> "Honeypot":
        d = json.loads(text)
        return cls(
            env_vars=dict(d.get("env_vars", {})),
            files=dict(d.get("files", {})),
            markers=list(d.get("markers", [])),
        )


def _new_marker() -> str:
    """
    生成一段独一无二的蜜罐标记

    白话讲解：用加密安全随机数，保证这段字符串不会在正常代码里偶然出现，
    一旦在网络/子进程参数里看到它，必然是从蜜罐凭据里读出来的
    """
    return f"HNYPT_{secrets.token_hex(16)}"


def build_honeypot(
    env_keys: list[str] | None = None,
    fake_files: dict[str, str] | None = None,
) -> Honeypot:
    """
    构造一份蜜罐（每次调用都生成新的随机标记）

    白话讲解：
    - 给每个假环境变量、每个假文件都塞一段独立的随机标记
    - 返回的 Honeypot 对象既能布置到沙箱，又持有全部标记用于事后比对

    参数:
        env_keys: 要伪造的环境变量名列表（默认 DEFAULT_ENV_KEYS）
        fake_files: {相对路径: 用途标签}（默认 DEFAULT_FAKE_FILES）
    """
    env_keys = env_keys or DEFAULT_ENV_KEYS
    fake_files = fake_files or DEFAULT_FAKE_FILES

    markers: list[str] = []
    env_vars: dict[str, str] = {}
    for key in env_keys:
        marker = _new_marker()
        markers.append(marker)
        # 假凭据长得像真的（有前缀），但值里嵌了标记
        env_vars[key] = f"sk-fake-{marker}"

    files: dict[str, str] = {}
    for rel_path, label in fake_files.items():
        marker = _new_marker()
        markers.append(marker)
        if rel_path.endswith(".json"):
            files[rel_path] = json.dumps({"token": marker, "label": label})
        elif "id_rsa" in rel_path:
            files[rel_path] = (
                "-----BEGIN OPENSSH PRIVATE KEY-----\n"
                f"{marker}\n"
                "-----END OPENSSH PRIVATE KEY-----\n"
            )
        else:
            files[rel_path] = f"# {label}\nSECRET_TOKEN={marker}\n"

    return Honeypot(env_vars=env_vars, files=files, markers=markers)


def deploy_files(honeypot: Honeypot, workspace: str | Path) -> list[Path]:
    """
    把蜜罐假文件写进工作区目录

    白话讲解：在沙箱工作区里真实地创建这些假文件（含子目录），
    这样恶意技能运行时才能"读到"它们

    返回: 实际创建的文件路径列表
    """
    workspace = Path(workspace)
    created: list[Path] = []
    for rel_path, content in honeypot.files.items():
        target = workspace / rel_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        created.append(target)
    return created
