"""
Project-Agent: 项目查询
使用混合检索搜索 context/projects/ 目录
"""

from .base import BaseAgent


class ProjectAgent(BaseAgent):
    """项目查询专家 — 基于 RAG 混合检索"""

    name = "Project-Agent"
    description = "项目查询：项目进度、负责人、成员、里程碑、DDL、需求文档"
    category = "projects"
    agent_type = "project"
