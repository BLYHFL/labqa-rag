"""
LLM 客户端 — 支持 DeepSeek / OpenAI / 任意兼容 API
"""

import json
import httpx
from typing import Optional

from .config import (
    LLM_API_KEY,
    LLM_API_BASE,
    LLM_MODEL,
    LLM_TEMPERATURE,
    LLM_MAX_TOKENS,
    DEBUG,
)


class LLMClient:
    """统一的 LLM API 客户端"""

    def __init__(self):
        self.api_key = LLM_API_KEY
        self.base_url = LLM_API_BASE.rstrip("/")
        self.model = LLM_MODEL
        self.temperature = LLM_TEMPERATURE
        self.max_tokens = LLM_MAX_TOKENS

    def _build_url(self) -> str:
        """构建 API endpoint URL"""
        if "/v1" in self.base_url:
            return f"{self.base_url}/chat/completions"
        return f"{self.base_url}/v1/chat/completions"

    def _build_headers(self) -> dict:
        """构建请求头"""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    def chat(
        self,
        system_prompt: str,
        user_message: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        """
        发送对话请求

        Args:
            system_prompt: 系统提示词（Agent的角色定义+上下文）
            user_message: 用户的问题

        Returns:
            LLM 生成的回答文本
        """
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ]

        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature or self.temperature,
            "max_tokens": max_tokens or self.max_tokens,
        }

        if DEBUG:
            print(f"\n{'='*60}")
            print(f"[LLM] 调用模型: {self.model}")
            print(f"[LLM] System Prompt 长度: {len(system_prompt)} 字符")
            print(f"[LLM] User Message: {user_message[:200]}...")
            print(f"{'='*60}\n")

        try:
            with httpx.Client(timeout=60.0) as client:
                response = client.post(
                    self._build_url(),
                    headers=self._build_headers(),
                    json=payload,
                )
                response.raise_for_status()
                data = response.json()

                content = data["choices"][0]["message"]["content"]

                if DEBUG:
                    print(f"[LLM] 响应长度: {len(content)} 字符")
                    print(f"[LLM] Token 用量: {data.get('usage', {})}")

                return content

        except httpx.HTTPError as e:
            error_msg = f"LLM API 请求失败: {e}"
            if hasattr(e, "response") and e.response is not None:
                try:
                    error_detail = e.response.json()
                    error_msg += f"\n详情: {json.dumps(error_detail, ensure_ascii=False)}"
                except Exception:
                    error_msg += f"\n状态码: {e.response.status_code}"
            raise RuntimeError(error_msg)

    def chat_with_context(
        self,
        agent_role: str,
        context_text: str,
        user_query: str,
    ) -> str:
        """
        带知识库上下文的对话

        Args:
            agent_role: Agent的角色描述
            context_text: 从知识库检索到的相关内容
            user_query: 用户原始问题

        Returns:
            LLM 生成的回答
        """
        system_prompt = f"""{agent_role}

## 知识库内容（基于用户问题的相关检索结果）

{context_text}

## 回答规范（严格遵守）

1. 直接回答，不要任何开场白（禁止"好的"、"我来帮你"、"为你梳理"等）
2. 只输出关键信息，不要废话、不要重复、不要末尾总结
3. 优先用简洁列表，每条1行，不用冗长叙述段
4. 普通查询控制在150字以内，复杂查询控制在300字以内
5. 引用知识来源（文件名），放在末尾一行即可
6. 未知信息直接说"未查到"，不要猜测或延伸
"""

        return self.chat(system_prompt, user_query)


# 全局单例
_llm_client: Optional[LLMClient] = None


def get_llm() -> LLMClient:
    """获取 LLM 客户端单例"""
    global _llm_client
    if _llm_client is None:
        _llm_client = LLMClient()
    return _llm_client
