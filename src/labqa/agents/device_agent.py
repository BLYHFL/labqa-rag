"""
Device-Agent: 设备/资产查询
使用混合检索搜索 context/devices/ 目录
"""

from typing import List
from .base import BaseAgent


class DeviceAgent(BaseAgent):
    """设备查询专家 — 基于 RAG 混合检索"""

    name = "Device-Agent"
    description = "设备/资产查询：服务器、GPU、网络设备、外勤设备的位置、状态、负责人"
    category = "devices"
    agent_type = "device"
