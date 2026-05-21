"""
Knowledge-Agent: 知识文档查询
负责检索 context/knowledge/ + context/guides/ 目录
回答论文、技术调研、流程规范相关问题
"""

from typing import List
from .base import BaseAgent


class KnowledgeAgent(BaseAgent):
    """知识文档查询专家"""

    name = "Knowledge-Agent"
    description = "知识文档查询：论文笔记、技术调研、流程规范、操作指南"
    category = None  # 搜索 knowledge + guides 两个目录

    role_prompt = """你是实验室知识管理员。直接回答文档问题，不要废话。

回答格式:
- 论文: 一句话总结 + 核心方法(1-2句) + 关键结论(1-2句)，不要展开
- 流程: 编号步骤，注意点用⚠️标注
- 对比: 简表，不要叙述
- 禁止开场白、禁止"好的"、禁止末尾总结
- 引用来源放最后一行"""

    def extract_search_keywords(self, query: str) -> List[str]:
        """提取知识文档相关的搜索关键词"""
        keywords = []

        query_lower = query.lower()

        # 论文名/技术名
        tech_names = {
            "dpo": ["dpo", "direct preference optimization", "偏好优化"],
            "rlhf": ["rlhf", "reinforcement learning", "人类反馈"],
            "ppo": ["ppo", "近端策略优化"],
            "kto": ["kto"],
            "transformer": ["transformer", "attention", "注意力"],
        }

        for tech, kws in tech_names.items():
            for kw in kws:
                if kw in query_lower:
                    keywords.append(tech)
                    break

        # 文档类型
        type_keywords = {
            "论文": ["论文", "paper", "文献", "文章"],
            "流程": ["流程", "步骤", "怎么做", "如何", "怎么", "指南", "教程"],
            "规范": ["规范", "标准", "要求", "规则", "policy"],
            "对比": ["区别", "对比", "比较", "哪个好", "优缺点", "分析"],
        }

        for typ, kws in type_keywords.items():
            for kw in kws:
                if kw in query_lower:
                    keywords.append(typ)
                    keywords.append(kw)

        # 具体流程/指南名
        guide_names = ["入职", "离职", "新人", "代码提交", "commit", "review",
                      "分支", "权限", "申请"]
        for name in guide_names:
            if name in query_lower:
                keywords.append(name)

        if not keywords:
            keywords = ["论文", "文档", "指南", "规范"]

        return list(set(keywords))

    def search_context(self, query: str, top_k: int = 5) -> str:
        """
        覆盖两个目录的搜索: knowledge + guides
        """
        keywords = self.extract_search_keywords(query)
        from ..config import DEBUG
        if DEBUG:
            print(f"\n[{self.name}] 检索关键词: {keywords}")
            print(f"[{self.name}] 检索分类: knowledge + guides")

        # 分别搜索两个目录，合并结果
        knowledge_text = self.store.get_context_text(keywords, category="knowledge", top_k=3)
        guides_text = self.store.get_context_text(keywords, category="guides", top_k=2)

        parts = []
        if knowledge_text and "未找到" not in knowledge_text:
            parts.append(knowledge_text)
        if guides_text and "未找到" not in guides_text:
            parts.append(guides_text)

        if not parts:
            return "（知识库中未找到相关内容）"

        return "\n\n═══════════════════════════════\n\n".join(parts)
