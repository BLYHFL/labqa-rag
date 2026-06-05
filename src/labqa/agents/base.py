"""
Agent 基类 — 所有子Agent的通用接口
底层检索已切换为 FAISS + BM25 混合检索
"""

from abc import ABC, abstractmethod
from typing import List, Optional

from ..config import DEBUG
from ..prompts import get_agent_prompt
from ..retriever import hybrid_search, search_by_category
from ..generator import generate_answer


class BaseAgent(ABC):
    """子Agent基类 — 基于 RAG 混合检索"""

    # 子类需覆盖
    name: str = "BaseAgent"
    description: str = ""
    category: Optional[str] = None  # 限定的知识库分类（None=全部）
    agent_type: str = ""  # device | project | knowledge

    def __init__(self, vectorstore=None, bm25_data=None, llm=None):
        self.vectorstore = vectorstore
        self.bm25_data = bm25_data
        self.llm = llm

    def set_dependencies(self, vectorstore, bm25_data, llm):
        """注入依赖"""
        self.vectorstore = vectorstore
        self.bm25_data = bm25_data
        self.llm = llm

    def search_context(self, query: str, top_k: int = 5) -> List:
        """
        使用混合检索检索相关知识库内容

        Args:
            query: 用户查询
            top_k: 返回文档数量

        Returns:
            检索到的文档列表
        """
        if self.vectorstore is None or self.bm25_data is None:
            raise RuntimeError(f"[{self.name}] 未注入索引依赖，请先调用 set_dependencies()")

        if self.category:
            # 限定分类检索
            docs = search_by_category(
                self.vectorstore, self.bm25_data,
                query, self.category, top_k=top_k,
            )
        else:
            # 全量检索
            docs = hybrid_search(
                self.vectorstore, self.bm25_data,
                query, top_k=top_k,
                verbose=DEBUG,
            )

        if DEBUG:
            print(f"\n[{self.name}] 混合检索: {len(docs)} 个文档块")
            for i, doc in enumerate(docs):
                source = doc.metadata.get("source", "?")
                print(f"  [{i+1}] {source}: {doc.page_content[:50]}...")

        return docs

    def answer(self, query: str) -> str:
        """
        完整 RAG 回答流程:
        1. 混合检索 → 2. Prompt 构建 → 3. LLM 生成
        """
        if self.llm is None:
            return "⚠️ LLM 未初始化，请稍后再试"

        # Step 1: 混合检索
        try:
            docs = self.search_context(query)
        except Exception as e:
            return f"⚠️ 检索失败: {e}"

        if not docs:
            return self._no_result_response(query)

        # Step 2: RAG 生成
        try:
            prompt_template = get_agent_prompt(self.agent_type)
            result = generate_answer(
                question=query,
                retrieved_docs=docs,
                llm=self.llm,
                system_prompt_template=prompt_template,
                verbose=DEBUG,
            )
            answer = result["answer"]
            sources = result["sources"]

            # 附加来源
            if sources and "来源" not in answer:
                answer += f"\n\n📎 来源: {', '.join(sources[:3])}"

            return answer
        except Exception as e:
            return f"⚠️ 生成回答失败: {e}"

    def _no_result_response(self, query: str) -> str:
        """无匹配结果时的默认回复"""
        return f"""在知识库中未找到与「{query}」相关的信息。

💡 建议:
- 尝试用不同关键词搜索
- 该信息可能尚未录入知识库
- 联系管理员补充相关文档

📋 LabQA-RAG 支持:
- 🖥 设备查询: GPU、服务器、测试车等
- 📂 项目查询: 进度、里程碑、负责人
- 📄 文档查询: 论文、流程、规范"""
