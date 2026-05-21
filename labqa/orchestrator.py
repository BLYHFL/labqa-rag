"""
LabQA Orchestrator — 主调度器
接收用户查询 → 意图识别 → 路由Agent → 整合回答
"""

from typing import Dict, Optional

from .router import recognize_intent, Intent, RoutingDecision
from .agents import get_agent, DeviceAgent, ProjectAgent, KnowledgeAgent
from .config import DEBUG, print_config


class Orchestrator:
    """LabQA 主调度器"""

    def __init__(self):
        self.agents = {
            "Device-Agent": get_agent("Device-Agent"),
            "Project-Agent": get_agent("Project-Agent"),
            "Knowledge-Agent": get_agent("Knowledge-Agent"),
        }

        # 意图到Agent的映射
        self.intent_agent_map = {
            Intent.DEVICE: "Device-Agent",
            Intent.PROJECT: "Project-Agent",
            Intent.KNOWLEDGE: "Knowledge-Agent",
        }

    def process(self, query: str) -> str:
        """
        处理用户查询的完整链路
        
        1. 意图识别
        2. 路由到Agent
        3. Agent检索 + LLM回答
        4. (混合意图) 合并多个Agent结果
        """
        # Step 1: 意图识别
        decision = recognize_intent(query)

        # Step 2: 未知意图
        if decision.intent == Intent.UNKNOWN:
            return self._unknown_intent_response()

        # Step 3: 路由到主Agent
        primary_agent = self.agents.get(decision.target_agent)
        if not primary_agent:
            return f"⚠️ Agent '{decision.target_agent}' 未注册"

        if DEBUG:
            print(f"\n[Orchestrator] 路由到: {decision.target_agent}")
            print(f"[Orchestrator] 意图: {decision.intent.value}, 置信度: {decision.confidence:.2f}")

        # Step 4: 主Agent回答
        primary_response = primary_agent.answer(query)

        # Step 5: 如果有混合意图，也查询次要Agent
        if decision.intent == Intent.MIXED and decision.secondary_intents:
            secondary_responses = []
            for sec_intent in decision.secondary_intents:
                sec_agent_name = self.intent_agent_map.get(sec_intent)
                if sec_agent_name and sec_agent_name != decision.target_agent:
                    sec_agent = self.agents.get(sec_agent_name)
                    if sec_agent:
                        if DEBUG:
                            print(f"[Orchestrator] 次要路由: {sec_agent_name}")
                        sec_response = sec_agent.answer(query)
                        secondary_responses.append(f"**📎 {sec_agent.description}**:\n{sec_response}")

            if secondary_responses:
                primary_response += "\n\n---\n\n" + "\n\n".join(secondary_responses)

        return primary_response

    def _unknown_intent_response(self) -> str:
        """无法识别意图时的引导回复"""
        return """不确定您的问题属于哪一类。LabQA 支持以下问题类型：

🖥 **设备查询** — 问设备位置、状态、负责人
   例: "GPU-A100-01还有空闲卡吗？" "自动驾驶测试车在哪？"

📂 **项目查询** — 问项目进度、里程碑、成员
   例: "LLM对齐项目进展如何？" "王五在忙什么项目？"

📄 **文档查询** — 问论文内容、流程规范、操作指南
   例: "DPO论文的核心方法是什么？" "怎么提交代码？"

💡 请换个方式描述您的问题，我会帮您找到答案。"""

    def stats(self) -> Dict:
        """系统状态"""
        from .context_store import get_store
        store = get_store()
        return {
            "agents": list(self.agents.keys()),
            "knowledge": store.get_stats(),
        }


# 全局单例
_orchestrator: Optional[Orchestrator] = None


def get_orchestrator() -> Orchestrator:
    """获取Orchestrator单例"""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = Orchestrator()
    return _orchestrator
