"""
Agent 包初始化
"""

from .base import BaseAgent
from .device_agent import DeviceAgent
from .project_agent import ProjectAgent
from .knowledge_agent import KnowledgeAgent

__all__ = ["BaseAgent", "DeviceAgent", "ProjectAgent", "KnowledgeAgent"]


def get_agent(name: str) -> BaseAgent:
    """根据名称获取Agent实例"""
    agents = {
        "Device-Agent": DeviceAgent(),
        "Project-Agent": ProjectAgent(),
        "Knowledge-Agent": KnowledgeAgent(),
    }
    return agents[name]
