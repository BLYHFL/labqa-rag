"""
Knowledge-Agent: 知识文档查询
使用混合检索搜索 context/knowledge/ + context/guides/ 目录
"""

from .base import BaseAgent


class KnowledgeAgent(BaseAgent):
    """知识文档查询专家 — 基于 RAG 混合检索（全量搜索）"""

    name = "Knowledge-Agent"
    description = "知识文档查询：论文笔记、技术调研、流程规范、操作指南"
    category = None  # 搜索全部目录（knowledge + guides + 其他）
    agent_type = "knowledge"
