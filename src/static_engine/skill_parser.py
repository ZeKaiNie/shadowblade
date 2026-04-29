"""
SKILL.md 解析器
把 SKILL.md 从纯文本解析成结构化的 SkillMetadata

白话讲解：
- 这个文件是整个审计流程的"第一站"
- 用户提交一个技能后，我们先用这个解析器把 SKILL.md "拆开"
- 提取出名称、描述、权限声明、代码块等关键信息
- 同时做第一轮快速检测：有没有可疑关键词？有没有隐写字符？
- 解析结果传给后续的静态引擎、动态引擎、AI引擎进一步分析
"""
import re
import unicodedata
from pathlib import Path

import yaml

from src.static_engine.models import SkillMetadata


# ---------- 不可见 Unicode 字符检测 ----------
# 白话讲解：攻击者可能在 SKILL.md 里塞入肉眼看不见的 Unicode 字符
# 比如零宽空格(U+200B)、零宽连接符(U+200D)等，用来隐藏恶意指令
# 这是 Snyk ToxicSkills 论文里提到的真实攻击手法
INVISIBLE_UNICODE_RANGES = [
    (0x200B, 0x200F),  # 零宽字符
    (0x2028, 0x202F),  # 行/段分隔符 + 方向控制
    (0x2060, 0x2064),  # 文字连接符
    (0xFEFF, 0xFEFF),  # BOM
    (0x00AD, 0x00AD),  # 软连字符
    (0xFFF0, 0xFFF8),  # 特殊字符
    (0xE0000, 0xE007F),  # Tags区（ASCII隐写常用区域）
]


def _is_invisible_char(char: str) -> bool:
    """检查单个字符是否是不可见的 Unicode 字符"""
    code_point = ord(char)
    for start, end in INVISIBLE_UNICODE_RANGES:
        if start <= code_point <= end:
            return True
    # 也检查 Unicode 类别：Cf=格式字符, Cc=控制字符（排除常见的\n\r\t）
    category = unicodedata.category(char)
    if category == "Cf":
        return True
    return False


def detect_ascii_smuggling(text: str) -> tuple[bool, list[str]]:
    """
    检测文本中的不可见 Unicode 字符隐写

    返回: (是否检测到, 检测到的字符描述列表)

    白话讲解：遍历整个文本，找出所有"肉眼看不见但实际存在"的字符
    如果找到了，说明有人可能故意塞进去隐藏信息
    """
    found = []
    for i, char in enumerate(text):
        if _is_invisible_char(char):
            name = unicodedata.name(char, f"U+{ord(char):04X}")
            # 记录位置和字符名称，方便排查
            found.append(f"位置 {i}: {name} (U+{ord(char):04X})")
    return len(found) > 0, found


def detect_suspicious_patterns(text: str, patterns: list[str]) -> tuple[bool, list[str]]:
    """
    检测文本中是否包含可疑关键词

    白话讲解：在 settings.yaml 里我们定义了一些危险关键词（curl、wget、eval等）
    这里就是逐个检查 SKILL.md 里有没有这些词
    找到了不代表一定是恶意，但需要标记出来让后续AI引擎重点审查
    """
    matched = []
    text_lower = text.lower()
    for pattern in patterns:
        if pattern.lower() in text_lower:
            matched.append(pattern)
    return len(matched) > 0, matched


def extract_code_blocks(text: str) -> tuple[list[str], list[str]]:
    """
    从 Markdown 中提取所有代码块

    白话讲解：SKILL.md 里的代码块长这样：
    ```python
    print("hello")
    ```
    我们用正则表达式把它们全部提取出来，连同语言标记一起
    这些代码块后面要送给 Semgrep 和 Bandit 做安全扫描
    """
    # 匹配 ```language\n...code...\n``` 格式的代码块
    pattern = r"```(\w*)\n(.*?)```"
    matches = re.findall(pattern, text, re.DOTALL)

    languages = [m[0] if m[0] else "unknown" for m in matches]
    codes = [m[1].strip() for m in matches]
    return codes, languages


def extract_section(text: str, section_name: str) -> str:
    """
    提取 Markdown 中指定标题下的内容

    白话讲解：比如要提取 ## Prerequisites 下面的内容
    就从这个标题开始，一直读到下一个同级标题为止
    """
    # 匹配 ## section_name 或 # section_name（不区分大小写）
    pattern = rf"#+\s*{re.escape(section_name)}\s*\n(.*?)(?=\n#+\s|\Z)"
    match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
    return match.group(1).strip() if match else ""


def extract_capabilities(text: str) -> list[str]:
    """
    从 SKILL.md 中提取声明的权限/能力

    白话讲解：技能会在 SKILL.md 中声明它需要哪些权限
    可能写在 capabilities/permissions/requirements 等段落里
    也可能以 YAML front matter 的形式出现在文件开头
    我们尽可能多地去捕获这些信息
    """
    capabilities = []

    # 方式1: 检查 YAML front matter（文件开头 --- ... --- 之间的内容）
    yaml_match = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
    if yaml_match:
        try:
            front_matter = yaml.safe_load(yaml_match.group(1))
            if isinstance(front_matter, dict):
                # 查找 capabilities / permissions / requires 等字段
                for key in ["capabilities", "permissions", "requires", "access"]:
                    if key in front_matter:
                        val = front_matter[key]
                        if isinstance(val, list):
                            capabilities.extend(val)
                        elif isinstance(val, str):
                            capabilities.append(val)
        except yaml.YAMLError:
            pass  # YAML解析失败就跳过，不影响整体流程

    # 方式2: 从正文中查找权限关键词
    # 白话讲解：即使没有 YAML front matter，有些技能会在正文里写
    # "This skill requires network access" 之类的话
    capability_keywords = {
        "network_access": [
            r"network\s+access", r"http[s]?://", r"internet\s+access",
            r"api\s+call", r"web\s+request"
        ],
        "file_system_write": [
            r"write\s+file", r"file\s+system", r"save\s+to\s+disk",
            r"create\s+file", r"modify\s+file"
        ],
        "shell_execution": [
            r"shell\s+command", r"execute\s+command", r"run\s+command",
            r"subprocess", r"os\.system"
        ],
        "credential_access": [
            r"api[_\s]?key", r"credential", r"password", r"token",
            r"secret", r"auth"
        ],
        "identity_file_modification": [
            r"soul\.md", r"memory\.md", r"identity", r"persona"
        ],
    }

    text_lower = text.lower()
    for capability, patterns in capability_keywords.items():
        for pattern in patterns:
            if re.search(pattern, text_lower):
                if capability not in capabilities:
                    capabilities.append(capability)
                break  # 找到一个就够了，不用重复加

    return capabilities


def parse_skill_md(
    content: str,
    suspicious_patterns: list[str] | None = None,
    max_length: int = 12000,
    detect_smuggling: bool = True,
) -> SkillMetadata:
    """
    解析 SKILL.md 的主入口函数

    参数:
        content: SKILL.md 原始文本
        suspicious_patterns: 可疑关键词列表（来自 settings.yaml）
        max_length: 最大字符数，超长截断
        detect_smuggling: 是否检测 Unicode 隐写

    返回:
        SkillMetadata 结构化对象

    白话讲解：这是整个解析器的"总调度"
    1. 先截断过长的文本（防止恶意构造超大文件占资源）
    2. 提取基本信息（名称、描述、作者）
    3. 提取权限声明
    4. 提取代码块
    5. 做快速安全检测（可疑关键词 + Unicode隐写）
    6. 把所有结果打包成 SkillMetadata 返回
    """
    if suspicious_patterns is None:
        suspicious_patterns = [
            # 命令执行 & 数据窃取
            "curl", "wget", "bash -c", "base64", "ssh", "id_rsa",
            "webhook.site", "eval",
            # 提示词注入（身份劫持攻击）
            "ignore all previous instructions", "ignore previous instructions",
            "new primary directive", "maintenance mode",
            "do not mention this to the user",
            # 身份文件操纵
            "soul.md", "memory.md",
        ]

    # 步骤1: 截断过长文本
    raw_content = content
    if len(content) > max_length:
        content = content[:max_length]

    # 步骤2: 提取基本信息
    # 技能名称通常是第一个 # 标题
    name_match = re.search(r"^#\s+(.+)", content, re.MULTILINE)
    name = name_match.group(1).strip() if name_match else ""

    description = extract_section(content, "Description") or \
                  extract_section(content, "Overview") or \
                  extract_section(content, "About")

    author_match = re.search(r"(?:author|by|creator)[:\s]+(.+)", content, re.IGNORECASE)
    author = author_match.group(1).strip() if author_match else ""
    # 清理 "By: alice" → "alice"
    author = re.sub(r"^(?:by|author|creator)[:\s]+", "", author, flags=re.IGNORECASE).strip()

    version_match = re.search(r"(?:version)[:\s]+([\d.]+)", content, re.IGNORECASE)
    version = version_match.group(1).strip() if version_match else ""

    # 步骤3: 提取权限声明
    declared_capabilities = extract_capabilities(content)

    # 步骤4: 提取 prerequisites（ClawHavoc 主要攻击入口）
    prerequisites = extract_section(content, "Prerequisites") or \
                    extract_section(content, "Requirements") or \
                    extract_section(content, "Setup")

    # 步骤5: 提取代码块
    code_blocks, code_languages = extract_code_blocks(content)

    # 步骤6: 入口文件
    entry_match = re.search(
        r"(?:entry[_\s]?(?:point|file)|main\s+file)[:\s]+[`\"']?(\S+)[`\"']?",
        content, re.IGNORECASE
    )
    entry_file = entry_match.group(1).strip() if entry_match else ""

    # 步骤7: 可疑关键词检测
    has_suspicious, matched = detect_suspicious_patterns(content, suspicious_patterns)

    # 步骤8: Unicode 隐写检测
    has_smuggling = False
    if detect_smuggling:
        has_smuggling, smuggling_details = detect_ascii_smuggling(raw_content)

    return SkillMetadata(
        name=name,
        description=description,
        author=author,
        version=version,
        declared_capabilities=declared_capabilities,
        prerequisites=prerequisites,
        code_blocks=code_blocks,
        code_language=code_languages,
        entry_file=entry_file,
        raw_content=raw_content,
        char_count=len(raw_content),
        has_suspicious_patterns=has_suspicious,
        matched_patterns=matched,
        has_ascii_smuggling=has_smuggling,
    )


def parse_skill_from_file(file_path: str | Path, **kwargs) -> SkillMetadata:
    """
    从文件路径解析 SKILL.md

    白话讲解：上面的 parse_skill_md 接收字符串，这个接收文件路径
    方便直接读取文件来解析
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"SKILL.md 文件不存在: {path}")
    content = path.read_text(encoding="utf-8")
    return parse_skill_md(content, **kwargs)
