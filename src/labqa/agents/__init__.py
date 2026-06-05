"""
Agent 层 — 基于混合检索的智能 Agent
"""

from .base import BaseAgent
from .device_agent import DeviceAgent
from .project_agent import ProjectAgent
from .knowledge_agent import KnowledgeAgent

__all__ = ["BaseAgent", "DeviceAgent", "ProjectAgent", "KnowledgeAgent"]


# Agent 注册表
AGENT_REGISTRY = {
    "Device-Agent": DeviceAgent,
    "Project-Agent": ProjectAgent,
    "Knowledge-Agent": KnowledgeAgent,
}


def get_agent(name: str) -> BaseAgent:
    """获取 Agent 实例"""
    agent_cls = AGENT_REGISTRY.get(name)
    if agent_cls is None:
        raise ValueError(f"未知 Agent: {name}，可用: {list(AGENT_REGISTRY.keys())}")
    return agent_cls()
