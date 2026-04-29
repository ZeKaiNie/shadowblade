# 静态审计引擎

## 文件清单

| 文件 | 作用 | 测试 |
|------|------|------|
| `src/static_engine/models.py` | Pydantic 数据模型 (SkillMetadata, SkillAuditResult) | - |
| `src/static_engine/skill_parser.py` | SKILL.md 解析器 | 12 tests |
| `src/static_engine/scanner.py` | Semgrep + Bandit + pip-audit 扫描 | 5 tests |

## 解析器功能（skill_parser.py）

- 提取基本信息：名称、描述、作者、版本
- 提取权限声明：YAML front matter + 正文关键词
- 提取代码块：带语言标记
- 可疑关键词检测：curl/wget/eval/base64 + 提示注入关键词
- Unicode 隐写检测：零宽字符、Tags 区不可见字符
- 超长文本截断：防恶意大文件

## 扫描器功能（scanner.py）

- **Semgrep**: 模式匹配扫描，支持自定义规则（`config/semgrep_rules/`）
- **Bandit**: Python 专用安全扫描（os.system、subprocess、pickle 等）
- **pip-audit**: 依赖漏洞扫描（CVE 检查）
- 统一 `ScanReport` 汇总所有工具发现

## 数据流

```
SKILL.md → skill_parser.parse_skill_md()
    → SkillMetadata（结构化数据）
        → scanner.scan_code_blocks()（代码块送检）
        → llm_judge.judge_skill()（AI 研判）
```
