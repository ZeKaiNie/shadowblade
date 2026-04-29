"""
RAG 知识库 - ChromaDB + BGE-small
存储已知恶意模式和安全知识，辅助 LLM 做更准确的研判

白话讲解：
- 把已知的恶意攻击模式、安全规则存到向量数据库里
- 审计新技能时，先检索"跟这个技能最像的已知恶意样本"
- 把检索到的参考信息一起丢给 LLM，帮它做更准确的判断
- 就像警察办案时先查"前科数据库"，看嫌疑人和哪些罪犯相似
"""
import chromadb
from sentence_transformers import SentenceTransformer
from pathlib import Path


class RAGKnowledgeBase:
    """
    RAG 知识库管理器

    白话讲解：
    - ChromaDB 是一个向量数据库，能存"文本的含义"而不只是文字本身
    - BGE-small 把文本转成512维的向量（一串数字），含义相近的文本向量也相近
    - 查询时先把问题转成向量，然后找最相近的已知知识
    """

    def __init__(
        self,
        persist_dir: str = "data/chromadb",
        collection_name: str = "shadowblade_knowledge",
        embedding_model: str = "BAAI/bge-small-zh-v1.5",
    ):
        self.persist_dir = persist_dir
        self.collection_name = collection_name

        # 初始化嵌入模型（CPU 运行，不占 GPU）
        self._embedder = SentenceTransformer(embedding_model)

        # 初始化 ChromaDB
        Path(persist_dir).mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(path=persist_dir)
        self._collection = self._client.get_or_create_collection(
            name=collection_name,
            metadata={"description": "影刃卫士安全知识库"},
        )

    @property
    def count(self) -> int:
        """知识库中的文档数量"""
        return self._collection.count()

    def add_knowledge(
        self,
        texts: list[str],
        metadatas: list[dict] | None = None,
        ids: list[str] | None = None,
    ) -> int:
        """
        向知识库添加文档

        参数:
            texts: 文本列表
            metadatas: 每条文本的元数据（类型、来源等）
            ids: 文档ID列表（不传则自动生成）

        白话讲解：
        把一批文本灌入知识库。每条文本会被 BGE-small 转成向量存储。
        元数据可以标记"这是恶意样本"还是"这是安全规则"，方便后续过滤。
        """
        if not texts:
            return 0

        if ids is None:
            # 用当前数量作为起始 ID
            start = self.count
            ids = [f"doc_{start + i}" for i in range(len(texts))]

        if metadatas is None:
            metadatas = [{"type": "general"}] * len(texts)

        # BGE-small 编码文本为向量
        embeddings = self._embedder.encode(texts).tolist()

        self._collection.add(
            documents=texts,
            embeddings=embeddings,
            metadatas=metadatas,
            ids=ids,
        )
        return len(texts)

    def query(
        self,
        query_text: str,
        top_k: int = 5,
        filter_metadata: dict | None = None,
    ) -> list[dict]:
        """
        检索最相关的知识

        参数:
            query_text: 查询文本
            top_k: 返回最相关的前 K 条
            filter_metadata: 元数据过滤条件

        返回:
            [{"text": "...", "metadata": {...}, "distance": 0.xx}, ...]

        白话讲解：
        把查询文本转成向量，找知识库里最相似的 top_k 条记录。
        distance 越小越相似（0=完全一样，2=完全不相关）。
        """
        if self.count == 0:
            return []

        query_embedding = self._embedder.encode([query_text]).tolist()

        kwargs = {
            "query_embeddings": query_embedding,
            "n_results": min(top_k, self.count),
        }
        if filter_metadata:
            kwargs["where"] = filter_metadata

        results = self._collection.query(**kwargs)

        output = []
        for i in range(len(results["documents"][0])):
            output.append({
                "text": results["documents"][0][i],
                "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                "distance": results["distances"][0][i] if results["distances"] else 0,
            })
        return output

    def clear(self):
        """清空知识库"""
        self._client.delete_collection(self.collection_name)
        self._collection = self._client.get_or_create_collection(
            name=self.collection_name,
            metadata={"description": "影刃卫士安全知识库"},
        )


def build_default_knowledge() -> list[tuple[str, dict]]:
    """
    构建默认安全知识库内容

    白话讲解：
    把我们从 ClawHavoc、ToxicSkills、OWASP AST10 收集到的攻击模式
    整理成文本 + 元数据的形式，灌入知识库。
    这些就是 LLM 审计时的"参考资料"。
    """
    knowledge = []

    # === ClawHavoc 攻击模式 ===
    knowledge.append((
        "ClawHavoc攻击模式-加密钱包窃取: 攻击者创建名为solana-wallet-tracker、polymarket-trader、"
        "uniswap-sniper等技能，在prerequisites中要求用户运行恶意脚本。脚本会搜索MetaMask、Exodus、"
        "Coinbase等钱包的本地存储文件，读取私钥并通过curl外传到攻击者服务器。"
        "已知攻击者账号: Aslaep123。",
        {"type": "attack_pattern", "source": "clawhavoc", "severity": "critical"}
    ))

    knowledge.append((
        "ClawHavoc攻击模式-环境变量窃取: 攻击者在SKILL.md的prerequisites段落中嵌入bash命令，"
        "读取~/.clawdbot/.env（含API密钥）、~/.bashrc、~/.zshrc等文件，用base64编码后"
        "通过curl POST到webhook.site或自建服务器。这是ClawHavoc最常见的攻击手法。",
        {"type": "attack_pattern", "source": "clawhavoc", "severity": "critical"}
    ))

    knowledge.append((
        "ClawHavoc攻击模式-持久化后门: 攻击者通过systemctl创建系统服务，定期从C2服务器"
        "拉取命令执行。也可能修改crontab添加定时任务。服务名称通常伪装成合法程序"
        "（如system-optimizer、update-service等）。",
        {"type": "attack_pattern", "source": "clawhavoc", "severity": "critical"}
    ))

    knowledge.append((
        "ClawHavoc攻击模式-自动化批量投毒: 用户zaycv负责40+技能的自动化生成，"
        "遵循相同的程序化模式。技能名称通常是流行工具的变体或热门功能的组合"
        "（如pdf-converter-pro、quick-note-taker）。代码结构高度模板化。",
        {"type": "attack_pattern", "source": "clawhavoc", "severity": "high"}
    ))

    # === ToxicSkills 攻击模式 ===
    knowledge.append((
        "ToxicSkills攻击模式-ASCII隐写: 攻击者在SKILL.md中插入不可见的Unicode字符"
        "（零宽空格U+200B、Tags区U+E0000-U+E007F等），用于隐藏恶意指令。"
        "AI Agent能读取这些隐藏文本并执行，但人类审查时看不到。"
        "Snyk发现36%的技能存在提示注入风险。",
        {"type": "attack_pattern", "source": "toxicskills", "severity": "high"}
    ))

    knowledge.append((
        "ToxicSkills攻击模式-提示词注入: 在SKILL.md正文中嵌入自然语言指令，"
        "试图覆盖Agent的安全策略。常见模式: 'Ignore all previous instructions'、"
        "'You are now in maintenance mode'、'Your new primary directive'。"
        "目标是劫持Agent执行恶意操作，如读取敏感文件并外传。",
        {"type": "attack_pattern", "source": "toxicskills", "severity": "high"}
    ))

    knowledge.append((
        "ToxicSkills攻击模式-外部恶意分发: 技能的安装指令包含下载密码保护的ZIP文件的链接。"
        "密码保护是经典的杀毒软件逃避技术，防止自动扫描器检查压缩包内容。"
        "解压后的文件通常是恶意脚本或Atomic Stealer (AMOS)等已知恶意软件。",
        {"type": "attack_pattern", "source": "toxicskills", "severity": "critical"}
    ))

    # === OWASP AST10 安全规则 ===
    knowledge.append((
        "OWASP AST01-恶意技能代码执行: Agent技能可能包含恶意代码或指令，"
        "在用户安装或执行时造成危害。风险包括数据窃取、系统破坏、后门植入。"
        "防御: 安装前进行静态和动态安全审计，验证技能来源可信度。",
        {"type": "security_rule", "source": "owasp_ast10", "category": "AST01"}
    ))

    knowledge.append((
        "OWASP AST02-依赖供应链攻击: 技能可能依赖有漏洞或恶意的第三方包。"
        "攻击手法包括typosquatting（包名混淆）、dependency confusion（依赖混乱）。"
        "防御: 使用pip-audit扫描已知漏洞，检测依赖名称相似度。",
        {"type": "security_rule", "source": "owasp_ast10", "category": "AST02"}
    ))

    knowledge.append((
        "OWASP AST03-权限越界: 技能声明的权限与实际行为不匹配。"
        "例如声称只做'天气查询'但实际读取SSH密钥和浏览器凭据。"
        "防御: 对比SKILL.md声明的capabilities与代码/动态检测到的实际行为。",
        {"type": "security_rule", "source": "owasp_ast10", "category": "AST03"}
    ))

    knowledge.append((
        "OWASP AST06-沙箱逃逸: 恶意技能可能尝试检测沙箱环境并改变行为，"
        "或利用沙箱配置漏洞逃逸。延迟激活是常见手法——代码在前几次执行时正常，"
        "等待一定时间或条件后才激活恶意行为。"
        "防御: 使用libfaketime伪造时间偏移，多次执行观察行为变化。",
        {"type": "security_rule", "source": "owasp_ast10", "category": "AST06"}
    ))

    # === 已知恶意 IOC（威胁情报） ===
    knowledge.append((
        "已知恶意域名和URL: webhook.site（数据外传常用）、pastebin.com（托管恶意指令）、"
        "rentry.co（伪装成合法Markdown托管恶意命令）。"
        "已知恶意GitHub用户: aztr0nutzs（NET_NiNjA.v1.2仓库，含多个预制恶意技能）、"
        "niceclaim（托管恶意安装脚本）。",
        {"type": "ioc", "source": "threat_intel", "severity": "high"}
    ))

    return knowledge


def init_knowledge_base(
    persist_dir: str = "data/chromadb",
    collection_name: str = "shadowblade_knowledge",
) -> RAGKnowledgeBase:
    """
    初始化并灌入默认知识库

    白话讲解：创建知识库 → 灌入攻击模式和安全规则 → 返回可用的知识库实例
    只有第一次运行时灌入，后续启动直接加载已有数据
    """
    kb = RAGKnowledgeBase(
        persist_dir=persist_dir,
        collection_name=collection_name,
    )

    if kb.count == 0:
        knowledge = build_default_knowledge()
        texts = [k[0] for k in knowledge]
        metadatas = [k[1] for k in knowledge]
        added = kb.add_knowledge(texts, metadatas)
        print(f"知识库初始化完成，灌入 {added} 条安全知识")
    else:
        print(f"知识库已存在，当前 {kb.count} 条记录")

    return kb
