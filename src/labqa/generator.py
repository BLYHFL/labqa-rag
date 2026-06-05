"""
LLM 生成模块 — Ollama 本地 + 云端 API 双轨适配

OllamaEmbeddings / OllamaChat 适配 LangChain 接口
ChatOpenAI 兼容 DeepSeek / OpenAI 等云端 API
"""

import os
from typing import List, Optional

from langchain_core.embeddings import Embeddings
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import BaseMessage
from langchain_core.outputs import ChatResult, ChatGeneration

from .config import (
    LLM_MODE,
    OLLAMA_LLM_MODEL,
    OLLAMA_EMBED_MODEL,
    LLM_API_KEY,
    LLM_API_BASE,
    LLM_MODEL,
    LLM_TEMPERATURE,
    LLM_MAX_TOKENS,
    DEBUG,
)


# ===== Ollama Embeddings 适配器 =====

class OllamaEmbeddings(Embeddings):
    """LangChain Embeddings 标准接口的 Ollama 适配器"""

    def __init__(self, model: str = "nomic-embed-text"):
        self.model_name = model

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return [self.embed_query(text) for text in texts]

    def embed_query(self, text: str) -> List[float]:
        import ollama
        result = ollama.embeddings(model=self.model_name, prompt=text)
        return result["embedding"]


# ===== Ollama Chat 适配器 =====

class OllamaChat:
    """Ollama LLM 轻量适配器（非完整 LangChain BaseChatModel，但接口兼容）"""

    def __init__(self, model: str = "deepseek-r1:1.5b"):
        self.model = model

    def invoke(self, messages: List[BaseMessage]) -> str:
        """处理 LangChain 消息格式 → Ollama API"""
        import ollama

        ollama_messages = []
        for msg in messages:
            role = "user"
            if hasattr(msg, "type"):
                if msg.type == "system":
                    role = "system"
                elif msg.type == "ai" or msg.type == "assistant":
                    role = "assistant"
            ollama_messages.append({"role": role, "content": msg.content})

        response = ollama.chat(model=self.model, messages=ollama_messages)
        return response["message"]["content"]

    def predict(self, text: str) -> str:
        """简化接口：直接输入文本"""
        from langchain_core.messages import HumanMessage
        return self.invoke([HumanMessage(content=text)])


# ===== 工厂函数 =====

def create_embeddings() -> Embeddings:
    """
    创建 Embedding 模型

    Ollama 模式: nomic-embed-text（本地，免费）
    云端模式: OpenAIEmbeddings（通过 OpenAI 兼容 API）
    """
    if LLM_MODE == "ollama":
        print(f"🔧 初始化 Ollama Embedding: {OLLAMA_EMBED_MODEL}")
        return OllamaEmbeddings(model=OLLAMA_EMBED_MODEL)
    else:
        from langchain_openai import OpenAIEmbeddings
        print(f"🔧 初始化云端 Embedding: {LLM_MODEL}")
        return OpenAIEmbeddings(
            api_key=LLM_API_KEY,
            base_url=LLM_API_BASE.rstrip("/") + "/v1" if "/v1" not in LLM_API_BASE else LLM_API_BASE,
            model=LLM_MODEL,
        )


def create_llm() -> BaseChatModel:
    """
    创建 LLM 模型

    Ollama 模式: DeepSeek-R1 1.5B（本地）
    云端模式: ChatOpenAI（兼容 DeepSeek / OpenAI）
    """
    if LLM_MODE == "ollama":
        print(f"🔧 初始化 Ollama LLM: {OLLAMA_LLM_MODEL}")
        return OllamaChat(model=OLLAMA_LLM_MODEL)
    else:
        from langchain_openai import ChatOpenAI
        print(f"🔧 初始化云端 LLM: {LLM_MODEL}")
        return ChatOpenAI(
            api_key=LLM_API_KEY,
            base_url=LLM_API_BASE,
            model=LLM_MODEL,
            temperature=LLM_TEMPERATURE,
            max_tokens=LLM_MAX_TOKENS,
        )


# ===== RAG 生成 =====

def generate_answer(
    question: str,
    retrieved_docs: List,
    llm,
    system_prompt_template: Optional[str] = None,
    verbose: bool = False,
) -> dict:
    """
    RAG 生成完整流程:

    1. 拼接检索到的文档为上下文
    2. 构造 Prompt
    3. 调用 LLM 生成回答

    Args:
        question: 用户问题
        retrieved_docs: 混合检索返回的文档列表
        llm: LLM 模型实例
        system_prompt_template: 可选的系统 Prompt 模板
        verbose: 是否打印详细过程

    Returns:
        {"answer": str, "sources": List[str], "docs": List}
    """
    # Step 1: 拼接上下文
    context = "\n\n---\n\n".join([
        f"[{doc.metadata.get('source', '?')}]\n{doc.page_content}"
        for doc in retrieved_docs
    ])

    # Step 2: 构造 Prompt
    if system_prompt_template:
        prompt_text = system_prompt_template.format(
            context=context,
            question=question,
        )
    else:
        prompt_text = PROMPT_TEMPLATE.format(
            context=context,
            question=question,
        )

    # Step 3: 调用 LLM
    if verbose:
        print(f"\n❓ 问题: {question}")
        print(f"📖 参考 {len(retrieved_docs)} 个文档片段：")
        for i, doc in enumerate(retrieved_docs, 1):
            preview = doc.page_content[:60].replace("\n", " ")
            source = doc.metadata.get("source", "?")
            print(f"   [{i}] {source} | {preview}...")

    # 判断 LLM 类型并调用
    if isinstance(llm, OllamaChat):
        raw_response = llm.predict(prompt_text)
    else:
        # LangChain ChatOpenAI
        from langchain_core.messages import SystemMessage, HumanMessage
        messages = [
            SystemMessage(content=prompt_text),
            HumanMessage(content=question),
        ]
        response = llm.invoke(messages)
        raw_response = response.content

    # Step 4: 提取来源
    sources = list(set(
        doc.metadata.get("source", "?") for doc in retrieved_docs
    ))

    if verbose:
        print(f"\n✅ 答案:\n{raw_response}")

    return {
        "answer": raw_response,
        "sources": sources,
        "docs": retrieved_docs,
    }


# ===== 默认 Prompt 模板 =====

PROMPT_TEMPLATE = """你是一个知识库问答助手。基于以下上下文回答问题。如果无法从上下文找到答案，请如实说明。

上下文:
{context}

---
问题: {question}

回答要求:
- 直接回答问题，不要开场白
- 简洁扼要，普通问题控制在150字以内
- 引用来源放在最后一行
- 不确定的信息直接说"未查到"

回答:"""


# 各 Agent 专用 Prompt 模板
AGENT_PROMPTS = {
    "device": """你是实验室设备管理员。基于设备信息回答问题，简洁直接。

## 设备信息

{context}

---
问题: {question}

回答格式:
- 单设备: 名称 | 位置 | 状态 | 负责人，一行搞定
- 设备清单: 简表列出，不要展开描述
- 禁止开场白、禁止"好的"、禁止末尾总结
- 引用来源放最后一行

回答:""",

    "project": """你是实验室项目管理助理。基于项目信息回答问题，简洁直接。

## 项目信息

{context}

---
问题: {question}

回答格式:
- 人员查询: 每项目一行: 项目名 | 角色 | 状态 | 关键节点
- 项目查询: 阶段 + 关键节点 + 风险
- 禁止开场白、禁止末尾总结
- 引用来源放最后一行

回答:""",

    "knowledge": """你是实验室知识管理员。基于知识库内容回答问题，简洁直接。

## 知识库内容

{context}

---
问题: {question}

回答格式:
- 论文: 一句话总结 + 核心方法 + 关键结论
- 流程: 编号步骤，注意点用⚠️标注
- 对比: 简表
- 禁止开场白、禁止"好的"、禁止末尾总结
- 引用来源放最后一行

回答:""",
}
