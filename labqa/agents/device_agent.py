"""
Device-Agent: 设备/资产查询
负责检索 context/devices/ 目录，回答硬件设备相关问题
"""

from typing import List
from .base import BaseAgent


class DeviceAgent(BaseAgent):
    """设备查询专家"""

    name = "Device-Agent"
    description = "设备/资产查询：服务器、GPU、网络设备、外勤设备的位置、状态、负责人"
    category = "devices"

    role_prompt = """你是实验室设备管理员。直接回答设备问题，不要废话。

回答格式:
- 单设备: 名称 | 位置 | 状态 | 负责人，一行搞定；空闲/占用情况用简表
- 设备清单: 简表列出，不要展开描述
- 禁止开场白、禁止"好的"、禁止末尾总结
- 引用来源放最后一行"""

    def extract_search_keywords(self, query: str) -> List[str]:
        """提取设备相关的搜索关键词"""
        keywords = []

        # 设备名/型号
        import re
        # 匹配型号: A100, H100, 4090, GPU-A100-01 等
        model_matches = re.findall(r'[A-Za-z]+[-\s]?\d+[-\s]?\d*', query)
        keywords.extend(model_matches)

        # 设备类型关键词
        type_keywords = {
            "gpu": ["gpu", "显卡", "算力", "gpu服务器", "gpu-"],
            "服务器": ["服务器", "server"],
            "工作站": ["工作站", "workstation"],
            "存储": ["nas", "存储", "硬盘", "数据"],
            "网络": ["交换机", "网络", "路由"],
            "测试车": ["测试车", "自动驾驶", "车辆", "car"],
            "采集": ["采集", "套件", "传感器", "激光雷达", "lidar"],
        }

        query_lower = query.lower()
        for _, kws in type_keywords.items():
            for kw in kws:
                if kw in query_lower:
                    keywords.append(kw)

        # 状态关键词
        status_words = ["空闲", "使用", "占用", "故障", "维修", "谁在用", "在哪"]
        for w in status_words:
            if w in query:
                keywords.append(w)

        # 设备编号/名称
        name_matches = re.findall(r'[A-Za-z]+-\d+', query)  # CAR-01, KIT-01
        keywords.extend(name_matches)

        # 名字
        for name in ["张三", "李四", "王五", "赵六"]:
            if name in query:
                keywords.append(name)

        # 默认至少搜索"设备"
        if not keywords:
            keywords = ["设备总览", "设备"]

        return list(set(keywords))  # 去重
