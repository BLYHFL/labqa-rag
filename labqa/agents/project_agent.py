"""
Project-Agent: 项目查询
负责检索 context/projects/ 目录，回答项目进度、人员、里程碑相关问题
"""

from typing import List
from .base import BaseAgent


class ProjectAgent(BaseAgent):
    """项目查询专家"""

    name = "Project-Agent"
    description = "项目查询：项目进度、负责人、成员、里程碑、DDL、需求文档"
    category = "projects"

    role_prompt = """你是实验室项目管理助理。简洁直接回答，不废话。

回答格式:
- 人员查询: 每项目一行: 项目名 | 角色 | 状态 | 关键节点(1个)
  例: "LLM对齐优化 | 工程实现 | 🔴紧急 | 改进方法验证中，ICML 6/15截稿"
- 项目查询: 阶段 + 2-3个关键节点(✅🔴⏳) + 如有风险一句话
- DDL评估: 一句话判断 + 关键日期
- 禁止开场白("好的""我来帮你")、禁止末尾"快速总结"
- 来源放最后一行"""

    def extract_search_keywords(self, query: str) -> List[str]:
        """提取项目相关的搜索关键词"""
        keywords = []

        query_lower = query.lower()

        # 项目名关键词
        project_names = {
            "llm对齐": ["llm", "rlhf", "对齐", "icml"],
            "自动驾驶": ["自动驾驶", "感知", "路测", "测试车", "数据采集"],
            "无人配送": ["无人配送", "园区", "配送"],
            "多模态融合": ["多模态", "融合", "cvpr"],
            "小样本": ["小样本", "持续学习", "neurips"],
            "世界模型": ["世界模型", "机器人", "规划"],
            "端侧部署": ["端侧", "部署", "量化", "蒸馏"],
            "gpu集群": ["集群", "slurm", "调度"],
        }

        for proj_name, kws in project_names.items():
            for kw in kws:
                if kw in query_lower:
                    keywords.append(kw)
                    keywords.append(proj_name)

        # 人员
        for name in ["张三", "李四", "王五", "赵六", "孙七", "周八", "吴九", "郑十"]:
            if name in query:
                keywords.append(name)

        # 状态/时间
        status_words = ["进度", "阶段", "里程碑", "截稿", "deadline", "ddl",
                       "赶得上", "来得及", "紧急", "阻塞", "完成", "目标"]
        for w in status_words:
            if w in query_lower:
                keywords.append(w)

        # 项目类型
        type_words = ["论文", "外勤", "测试", "探索", "预研", "运营", "管理"]
        for w in type_words:
            if w in query_lower:
                keywords.append(w)

        # 会议/期刊
        conf_words = ["icml", "neurips", "cvpr", "iccv", "eccv", "iclr", "aaai"]
        for w in conf_words:
            if w in query_lower:
                keywords.append(w)

        if not keywords:
            keywords = ["项目总览", "项目"]

        return list(set(keywords))
