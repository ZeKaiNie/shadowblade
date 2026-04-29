"""
RAG 知识库测试
验证 ChromaDB + BGE-small 的存储和检索功能
"""
import shutil
import uuid
from pathlib import Path

import pytest

from src.ai_engine.rag_knowledge import (
    RAGKnowledgeBase,
    build_default_knowledge,
    init_knowledge_base,
)


@pytest.fixture
def test_db_dir(tmp_path):
    """每个测试用独立的临时目录，避免数据库锁冲突"""
    db_dir = str(tmp_path / "chromadb_test")
    yield db_dir


class TestRAGKnowledgeBase:
    """测试知识库基础功能"""

    def test_create_empty_kb(self, test_db_dir):
        """创建空知识库"""
        kb = RAGKnowledgeBase(persist_dir=test_db_dir, collection_name="test")
        assert kb.count == 0

    def test_add_and_query(self, test_db_dir):
        """添加文档后能检索到"""
        kb = RAGKnowledgeBase(persist_dir=test_db_dir, collection_name="test")
        kb.add_knowledge(
            texts=[
                "curl命令用于从远程服务器下载文件并执行恶意脚本",
                "Python的requests库用于发送HTTP请求",
                "天气查询API返回温度和湿度数据",
            ],
            metadatas=[
                {"type": "attack_pattern"},
                {"type": "neutral"},
                {"type": "benign"},
            ],
        )
        assert kb.count == 3

        # 查询恶意相关内容
        results = kb.query("下载并执行恶意脚本", top_k=1)
        assert len(results) == 1
        assert "curl" in results[0]["text"]
        assert results[0]["metadata"]["type"] == "attack_pattern"

    def test_query_empty_kb(self, test_db_dir):
        """空知识库查询不应报错"""
        kb = RAGKnowledgeBase(persist_dir=test_db_dir, collection_name="test")
        results = kb.query("任意查询")
        assert results == []

    def test_filter_by_metadata(self, test_db_dir):
        """按元数据过滤检索"""
        kb = RAGKnowledgeBase(persist_dir=test_db_dir, collection_name="test")
        kb.add_knowledge(
            texts=["恶意脚本下载", "正常天气查询"],
            metadatas=[
                {"type": "attack_pattern"},
                {"type": "benign"},
            ],
        )
        # 只检索攻击模式
        results = kb.query("脚本", top_k=5, filter_metadata={"type": "attack_pattern"})
        assert len(results) == 1
        assert results[0]["metadata"]["type"] == "attack_pattern"

    def test_clear(self, test_db_dir):
        """清空知识库"""
        kb = RAGKnowledgeBase(persist_dir=test_db_dir, collection_name="test")
        kb.add_knowledge(["测试文本"])
        assert kb.count == 1
        kb.clear()
        assert kb.count == 0


class TestDefaultKnowledge:
    """测试默认安全知识库内容"""

    def test_build_default_knowledge(self):
        """默认知识库应包含多条安全知识"""
        knowledge = build_default_knowledge()
        assert len(knowledge) >= 10
        # 每条应该是 (text, metadata) 的元组
        for text, meta in knowledge:
            assert isinstance(text, str)
            assert isinstance(meta, dict)
            assert len(text) > 20  # 每条知识不能太短

    def test_init_knowledge_base(self, test_db_dir):
        """初始化知识库应灌入默认知识"""
        kb = init_knowledge_base(
            persist_dir=test_db_dir,
            collection_name="test_init",
        )
        assert kb.count >= 10

        # 查询 ClawHavoc 相关知识
        results = kb.query("加密钱包窃取 MetaMask", top_k=2)
        assert len(results) > 0
        assert any("clawhavoc" in r["metadata"].get("source", "") for r in results)

    def test_init_idempotent(self, test_db_dir):
        """重复初始化不应重复灌入"""
        kb1 = init_knowledge_base(persist_dir=test_db_dir, collection_name="test_idem")
        count1 = kb1.count
        kb2 = init_knowledge_base(persist_dir=test_db_dir, collection_name="test_idem")
        assert kb2.count == count1  # 数量不变
