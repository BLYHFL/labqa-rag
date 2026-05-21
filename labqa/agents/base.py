"""
Agent 基类 — 定义所有子Agent的通用接口
"""

from abc import ABC, abstractmethod
from typing import List, Optional

from ..context_store import get_store, ContextStore
from ..llm import get_llm, LLMClient
from ..config import DEBUG


class BaseAgent(ABC):
    """子Agent基类"""

    # 子类需覆盖的属性
    name: str = "BaseAgent"
    description: str = ""
    category: str = ""  # 对应 context/ 下的子目录
    role_prompt: str = ""  # 注入 LLM system prompt 的角色描述

    def __init__(self):
        self.store: ContextStore = get_store()
        self.llm: LLMClient = get_llm()

    @abstractmethod
    def extract_search_keywords(self, query: str) -> List[str]:
        """
        从用户查询中提取检索关键词
        不同 Agent 的提取策略不同
        """
        pass

    def search_context(self, query: str, top_k: int = 5) -> str:
        """
        检索相关知识库内容
        """
        keywords = self.extract_search_keywords(query)

        if DEBUG:
            print(f"\n[{self.name}] 检索关键词: {keywords}")
            print(f"[{self.name}] 检索分类: {self.category}")

        return self.store.get_context_text(
            keywords=keywords,
            category=self.category,
            top_k=top_k,
        )

    def answer(self, query: str) -> str:
        """
        完整回答流程:
        1. 检索知识库
        2. 构造 LLM prompt
        3. 调用 LLM 生成回答
        """
        # 1. 检索
        context_text = self.search_context(query)

        if DEBUG:
            print(f"\n[{self.name}] 检索到上下文: {len(context_text)} 字符")

        # 2. 如果没有检索到内容，直接返回
        if "未找到相关内容" in context_text:
            return self._no_result_response(query)

        # 3. 调用 LLM
        try:
            response = self.llm.chat_with_context(
                agent_role=self.role_prompt,
                context_text=context_text,
                user_query=query,
            )
            return response
        except Exception as e:
            return f"⚠️ 回答生成失败: {e}\n\n检索到的知识库内容如下，请人工参考:\n\n{context_text[:1000]}"

    def _no_result_response(self, query: str) -> str:
        """无匹配结果时的默认回复"""
        return f"""在知识库中未找到与 "{query}" 相关的信息。

💡 **建议**:
- 尝试用不同关键词搜索
- 该信息可能尚未录入知识库
- 联系管理员补充相关文档

📋 当前知识库覆盖范围:
- 🖥 设备: {self._count_category('devices')} 个文件
- 📂 项目: {self._count_category('projects')} 个文件
- 📄 文档: {self._count_category('knowledge')} 个文件
- 📋 指南: {self._count_category('guides')} 个文件"""

    def _count_category(self, category: str) -> int:
        stats = self.store.get_stats()
        return stats["by_category"].get(category, 0)
