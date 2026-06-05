"""
LabQA-RAG 核心模块测试

运行: pytest tests/ -v
"""

import sys
import tempfile
import shutil
from pathlib import Path
import pytest

# 确保 src/ 在 Python path 中
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


class TestConfig:
    """配置模块测试"""

    def test_config_loads(self):
        """配置能正常加载"""
        from labqa.config import (
            LLM_MODE, CONTEXT_DIR, FAISS_INDEX_DIR, BM25_INDEX_PATH,
            RETRIEVE_K, FUSION_K, RRF_K, CHUNK_SIZE,
        )
        assert LLM_MODE in ("ollama", "cloud")
        assert isinstance(RETRIEVE_K, int) and RETRIEVE_K > 0
        assert isinstance(FUSION_K, int) and FUSION_K > 0
        assert isinstance(RRF_K, int) and RRF_K > 0
        assert isinstance(CHUNK_SIZE, int) and CHUNK_SIZE > 0

    def test_validate(self):
        """配置校验"""
        from labqa.config import validate
        issues = validate()  # 不做硬断言，环境可能未配置完整
        assert isinstance(issues, list)


class TestIngest:
    """入库模块测试"""

    def test_load_markdown_files(self):
        """加载 Markdown 文件"""
        from labqa.ingest import load_markdown_files
        from labqa.config import CONTEXT_DIR

        docs = load_markdown_files(CONTEXT_DIR)
        # 无论有没有文件，都应返回列表
        assert isinstance(docs, list)

        if docs:
            doc = docs[0]
            assert hasattr(doc, 'page_content')
            assert hasattr(doc, 'metadata')
            assert 'source' in doc.metadata
            assert 'category' in doc.metadata

    def test_split_documents(self):
        """文本分块"""
        from labqa.ingest import split_documents
        from langchain_core.documents import Document as LCDocument

        docs = [
            LCDocument(
                page_content="这是一个测试文档。" * 50,
                metadata={"source": "test.md", "category": "test"}
            )
        ]

        chunks = split_documents(docs, chunk_size=100, chunk_overlap=20)
        assert len(chunks) > 0

        # 验证分块后元数据保留
        for chunk in chunks:
            assert chunk.metadata.get("source") == "test.md"

    def test_check_indexes(self):
        """索引状态检查"""
        from labqa.ingest import check_indexes

        status = check_indexes()
        assert isinstance(status, dict)
        assert "faiss_exists" in status
        assert "bm25_exists" in status
        assert "context_exists" in status
        assert "document_count" in status


class TestRouter:
    """路由模块测试"""

    def test_recognize_device_intent(self):
        """识别设备意图"""
        from labqa.router import recognize_intent, Intent

        queries = [
            ("GPU-A100-01还有空闲卡吗？", Intent.DEVICE),
            ("服务器在哪", Intent.DEVICE),
            # "测试车谁在用" 中"测试"同时命中PROJECT关键词，路由为MIXED，但主意图仍是DEVICE
            ("测试车谁在用", Intent.MIXED),
        ]

        for q, expected in queries:
            decision = recognize_intent(q)
            assert decision.intent == expected, f"Query '{q}' should be {expected}"
            if expected == Intent.MIXED:
                assert decision.target_agent == "Device-Agent"

    def test_recognize_project_intent(self):
        """识别项目意图"""
        from labqa.router import recognize_intent, Intent

        queries = [
            "LLM对齐项目进展如何？",
            "ICML截稿日期是什么？",
            "王五在做什么项目？",
        ]

        for q in queries:
            decision = recognize_intent(q)
            assert decision.intent == Intent.PROJECT, f"Query '{q}' should be PROJECT"

    def test_recognize_knowledge_intent(self):
        """识别文档意图"""
        from labqa.router import recognize_intent, Intent

        queries = [
            "DPO论文的核心方法是什么？",
            "怎么提交代码？",
            "新人入职流程是什么？",
        ]

        for q in queries:
            decision = recognize_intent(q)
            assert decision.intent == Intent.KNOWLEDGE, f"Query '{q}' should be KNOWLEDGE"

    def test_unknown_intent(self):
        """未知意图"""
        from labqa.router import recognize_intent, Intent

        # 完全无关的输入
        decision = recognize_intent("今天天气真好")
        # 可能是 UNKNOWN 或某个低置信度意图
        assert decision.intent in (
            Intent.UNKNOWN, Intent.DEVICE, Intent.PROJECT, Intent.KNOWLEDGE
        )

    def test_extract_keywords(self):
        """关键词提取"""
        from labqa.router import extract_keywords

        keywords = extract_keywords("GPU-A100-01服务器在哪？")
        assert len(keywords) > 0
        assert any("gpu" in kw.lower() or "a100" in kw.lower() for kw in keywords)


class TestRRF:
    """RRF 融合算法测试"""

    def test_reciprocal_rank_fusion_basic(self):
        """RRF 基本功能"""
        from labqa.retriever import reciprocal_rank_fusion
        from langchain_core.documents import Document as LCDocument

        doc1 = LCDocument(page_content="文档A", metadata={"source": "a.md"})
        doc2 = LCDocument(page_content="文档B", metadata={"source": "b.md"})
        doc3 = LCDocument(page_content="文档C", metadata={"source": "c.md"})

        # 两路检索结果
        results1 = [
            {"doc": doc1, "score": 0.9},
            {"doc": doc2, "score": 0.7},
        ]
        results2 = [
            {"doc": doc2, "score": 1.0},  # doc2 在第二路排第一
            {"doc": doc3, "score": 0.5},
        ]

        fused = reciprocal_rank_fusion([results1, results2], k=60)

        assert len(fused) == 3  # 唯一文档去重
        # doc2 应该排最前（在两路都有高排名）
        assert fused[0]["doc"].page_content == "文档B"

    def test_rrf_single_list(self):
        """RRF 单路搜索"""
        from labqa.retriever import reciprocal_rank_fusion
        from langchain_core.documents import Document as LCDocument

        docs = [
            LCDocument(page_content=f"文档{i}", metadata={"source": f"{i}.md"})
            for i in range(5)
        ]
        results = [{"doc": doc, "score": 1.0} for doc in docs]

        fused = reciprocal_rank_fusion([results], k=60)
        assert len(fused) == len(docs)
        # 应保持原顺序
        for i, item in enumerate(fused):
            assert item["doc"].page_content == f"文档{i}"


class TestPrompts:
    """Prompt 模板测试"""

    def test_default_prompt(self):
        """默认 Prompt 模板"""
        from labqa.prompts import DEFAULT_RAG_PROMPT

        filled = DEFAULT_RAG_PROMPT.format(
            context="测试上下文",
            question="测试问题",
        )
        assert "测试上下文" in filled
        assert "测试问题" in filled

    def test_get_agent_prompt(self):
        """获取 Agent 专用 Prompt"""
        from labqa.prompts import get_agent_prompt

        for agent_type in ("device", "project", "knowledge"):
            prompt = get_agent_prompt(agent_type)
            assert isinstance(prompt, str)
            assert "{context}" in prompt
            assert "{question}" in prompt

        # 未知类型应返回默认 Prompt
        prompt = get_agent_prompt("unknown")
        assert isinstance(prompt, str)

    def test_agent_prompts_all_have_placeholders(self):
        """所有 Agent Prompt 都包含必要的占位符"""
        from labqa.prompts import (
            DEVICE_PROMPT, PROJECT_PROMPT, KNOWLEDGE_PROMPT,
            UNKNOWN_INTENT_PROMPT, DEFAULT_RAG_PROMPT,
        )

        prompts = [
            DEVICE_PROMPT, PROJECT_PROMPT, KNOWLEDGE_PROMPT,
            DEFAULT_RAG_PROMPT,
        ]
        for prompt in prompts:
            assert "{context}" in prompt
            assert "{question}" in prompt


class TestGenerator:
    """生成模块测试（需要 Ollama 运行时）"""

    @pytest.mark.skip(reason="需要 Ollama 运行环境")
    def test_ollama_embeddings(self):
        """Ollama Embeddings"""
        from labqa.generator import OllamaEmbeddings

        embed = OllamaEmbeddings(model="nomic-embed-text")
        vector = embed.embed_query("测试文本")
        assert isinstance(vector, list)
        assert len(vector) > 0
        assert all(isinstance(v, float) for v in vector)

    @pytest.mark.skip(reason="需要 Ollama 运行环境")
    def test_ollama_chat(self):
        """Ollama Chat"""
        from labqa.generator import OllamaChat
        from langchain_core.messages import HumanMessage

        llm = OllamaChat(model="deepseek-r1:1.5b")
        response = llm.invoke([HumanMessage(content="你好，1+1=?")])
        assert isinstance(response, str)
        assert len(response) > 0

    def test_create_embeddings_factory(self):
        """Embedding 工厂函数"""
        from labqa.generator import create_embeddings
        from labqa.config import LLM_MODE

        embed = create_embeddings()

        if LLM_MODE == "ollama":
            from labqa.generator import OllamaEmbeddings
            assert isinstance(embed, OllamaEmbeddings)


class TestAgents:
    """Agent 模块测试"""

    def test_agent_registry(self):
        """Agent 注册表"""
        from labqa.agents import AGENT_REGISTRY, get_agent

        assert "Device-Agent" in AGENT_REGISTRY
        assert "Project-Agent" in AGENT_REGISTRY
        assert "Knowledge-Agent" in AGENT_REGISTRY

        for name in AGENT_REGISTRY:
            agent = get_agent(name)
            assert agent.name == name

    def test_agent_attributes(self):
        """Agent 属性"""
        from labqa.agents import DeviceAgent, ProjectAgent, KnowledgeAgent

        device = DeviceAgent()
        assert device.name == "Device-Agent"
        assert device.category == "devices"
        assert device.agent_type == "device"

        project = ProjectAgent()
        assert project.name == "Project-Agent"
        assert project.category == "projects"
        assert project.agent_type == "project"

        knowledge = KnowledgeAgent()
        assert knowledge.name == "Knowledge-Agent"
        assert knowledge.category is None  # 全量搜索
        assert knowledge.agent_type == "knowledge"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
