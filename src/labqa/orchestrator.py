"""
LabQA Orchestrator — 主调度器
接收用户查询 → 意图识别 → 路由Agent → RAG回答
"""

from typing import Dict, Optional

from .router import recognize_intent, Intent
from .agents import get_agent, DeviceAgent, ProjectAgent, KnowledgeAgent
from .config import DEBUG
from .retriever import load_indexes, hybrid_search
from .generator import create_llm, create_embeddings, generate_answer, AGENT_PROMPTS


class Orchestrator:
    """LabQA-RAG 主调度器"""

    def __init__(self):
        self.agents: Dict[str, any] = {}
        self.vectorstore = None
        self.bm25_data = None
        self.llm = None
        self.initialized = False

    def initialize(self):
        """初始化：加载索引 + LLM + Agent"""
        if self.initialized:
            return

        print("🚀 初始化 LabQA-RAG...\n")

        # 1. 加载 Embedding 模型
        embed_model = create_embeddings()

        # 2. 加载索引
        self.vectorstore, self.bm25_data = load_indexes(embed_model)

        if self.vectorstore is None or self.bm25_data is None:
            print("⚠️ 索引未构建！请先运行入库:")
            print("   python -m labqa.ingest")
            print("\n🧪 将以离线模式启动（仅意图识别，无检索能力）\n")

        # 3. 加载 LLM
        try:
            self.llm = create_llm()
        except Exception as e:
            print(f"⚠️ LLM 初始化失败: {e}")
            print("   将在离线模式下运行（无 LLM 生成）\n")

        # 4. 初始化 Agent
        self._init_agents()

        self.initialized = True

    def _init_agents(self):
        """初始化所有 Agent 并注入依赖"""
        agent_classes = {
            "Device-Agent": DeviceAgent,
            "Project-Agent": ProjectAgent,
            "Knowledge-Agent": KnowledgeAgent,
        }

        for name, cls in agent_classes.items():
            agent = cls()
            agent.set_dependencies(self.vectorstore, self.bm25_data, self.llm)
            self.agents[name] = agent

        if DEBUG:
            print(f"[Orchestrator] 已注册 Agent: {list(self.agents.keys())}")

    def process(self, query: str) -> str:
        """
        处理用户查询的完整链路:

        1. 意图识别 → 2. 路由 Agent → 3. Agent 混合检索 → 4. LLM 生成
        """
        if not self.initialized:
            self.initialize()

        # Step 1: 意图识别
        decision = recognize_intent(query)

        # Step 2: 未知意图 → 使用全量混合检索
        if decision.intent == Intent.UNKNOWN:
            return self._unknown_intent_response(query)

        # Step 3: 路由到主 Agent
        primary_agent = self.agents.get(decision.target_agent)
        if not primary_agent:
            return f"⚠️ Agent '{decision.target_agent}' 未注册"

        if DEBUG:
            print(f"\n[Orchestrator] 路由到: {decision.target_agent}")
            print(f"[Orchestrator] 意图: {decision.intent.value}, "
                  f"置信度: {decision.confidence:.2f}")

        # Step 4: Agent RAG 回答
        try:
            response = primary_agent.answer(query)
        except Exception as e:
            return f"⚠️ 处理失败: {e}"

        # Step 5: 混合意图 → 也查询次要 Agent
        if decision.intent == Intent.MIXED and decision.secondary_intents:
            secondary_responses = []
            intent_agent_map = {
                Intent.DEVICE: "Device-Agent",
                Intent.PROJECT: "Project-Agent",
                Intent.KNOWLEDGE: "Knowledge-Agent",
            }

            for sec_intent in decision.secondary_intents:
                sec_agent_name = intent_agent_map.get(sec_intent)
                if sec_agent_name and sec_agent_name != decision.target_agent:
                    sec_agent = self.agents.get(sec_agent_name)
                    if sec_agent:
                        if DEBUG:
                            print(f"[Orchestrator] 次要路由: {sec_agent_name}")
                        try:
                            sec_response = sec_agent.answer(query)
                            secondary_responses.append(
                                f"**📎 {sec_agent.description}**:\n{sec_response}"
                            )
                        except Exception:
                            pass

            if secondary_responses:
                response += "\n\n---\n\n" + "\n\n".join(secondary_responses)

        return response

    def _unknown_intent_response(self, query: str) -> str:
        """无法识别意图时：用全量混合检索兜底"""
        # 如果索引可用，用全量混合检索尝试回答
        if self.vectorstore and self.bm25_data and self.llm:
            try:
                docs = hybrid_search(
                    self.vectorstore, self.bm25_data,
                    query, top_k=5, verbose=DEBUG,
                )

                if docs:
                    result = generate_answer(
                        question=query,
                        retrieved_docs=docs,
                        llm=self.llm,
                        verbose=DEBUG,
                    )
                    return result["answer"]
            except Exception:
                pass

        # 回退：引导用户
        return """不确定您的问题属于哪一类。LabQA-RAG 支持以下问题类型：

🖥 **设备查询** — 问设备位置、状态、负责人
   例: "GPU-A100-01还有空闲卡吗？" "自动驾驶测试车在哪？"

📂 **项目查询** — 问项目进度、里程碑、成员
   例: "LLM对齐项目进展如何？" "王五在忙什么项目？"

📄 **文档查询** — 问论文内容、流程规范、操作指南
   例: "DPO论文的核心方法是什么？" "怎么提交代码？"

💡 请换个方式描述您的问题，我会帮您找到答案。"""

    def stats(self) -> Dict:
        """系统状态"""
        from .ingest import check_indexes
        idx_status = check_indexes()
        return {
            "version": "2.0.0",
            "agents": list(self.agents.keys()),
            "llm_mode": "ollama" if hasattr(self.llm, 'model') and not hasattr(self.llm, 'api_key') else "cloud",
            "indexes": idx_status,
        }

    def reload(self):
        """重新加载知识库和索引"""
        print("🔄 重新加载索引...")
        embed_model = create_embeddings()
        self.vectorstore, self.bm25_data = load_indexes(embed_model)
        self._init_agents()
        print("✅ 索引已更新")


# 全局单例
_orchestrator: Optional[Orchestrator] = None


def get_orchestrator() -> Orchestrator:
    """获取 Orchestrator 单例"""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = Orchestrator()
    return _orchestrator
