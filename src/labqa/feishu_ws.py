"""
飞书 WebSocket 长连接集成
无需公网 IP，通过 lark-oapi SDK 接收消息

基于原 labqa/feishu_ws.py 改造，底层切换到 RAG 混合检索
"""

import sys
import json
import time
import hashlib
from pathlib import Path
from typing import Set, Dict

# 确保 src/ 在 Python path 中
sys.path.insert(0, str(Path(__file__).parent.parent))

from .config import (
    FEISHU_APP_ID, FEISHU_APP_SECRET, DEBUG,
)


# 消息去重
_seen_message_ids: Set[str] = set()
_chat_content_hashes: Dict[str, Dict[str, float]] = {}  # chat_id → {hash: timestamp}


def _is_duplicate(message_id: str, chat_id: str, content: str) -> bool:
    """两层去重：message_id + 内容哈希（30秒窗口）"""
    # 层1: message_id 去重
    if message_id and message_id in _seen_message_ids:
        return True

    if message_id:
        _seen_message_ids.add(message_id)
        # 限制内存
        if len(_seen_message_ids) > 10000:
            _seen_message_ids.clear()

    # 层2: 内容哈希去重（30秒窗口）
    content_hash = hashlib.md5(content.encode()).hexdigest()
    now = time.time()
    if chat_id not in _chat_content_hashes:
        _chat_content_hashes[chat_id] = {}

    # 清理过期哈希
    _chat_content_hashes[chat_id] = {
        h: ts for h, ts in _chat_content_hashes[chat_id].items()
        if now - ts < 30
    }

    if content_hash in _chat_content_hashes[chat_id]:
        return True

    _chat_content_hashes[chat_id][content_hash] = now
    return False


def _handle_message(chat_id: str, message_id: str, content: str, orchestrator) -> str:
    """处理单条消息"""
    if DEBUG:
        print(f"[Feishu] 收到消息: chat_id={chat_id[:10]}..., content={content[:80]}...")

    # 去重
    if _is_duplicate(message_id, chat_id, content):
        if DEBUG:
            print("[Feishu] 消息重复，已跳过")
        return ""

    # 调用 Orchestrator
    try:
        response = orchestrator.process(content)
        return response
    except Exception as e:
        return f"⚠️ 处理出错: {e}"


def _send_message(lark_client, chat_id: str, content: str, msg_type: str = "text"):
    """发送消息"""
    try:
        if msg_type == "text":
            # 飞书文本消息最长 20000 字符
            truncated = content[:19900] + ("..." if len(content) > 19900 else "")
            lark_client.im.message.create({
                "receive_id": chat_id,
                "msg_type": "text",
                "content": json.dumps({"text": truncated}),
            })
    except Exception as e:
        print(f"[Feishu] 发送失败: {e}")


def start():
    """启动飞书 WebSocket 长连接服务"""
    from lark_oapi.event import EventDispatcherHandler
    from lark_oapi.ws import Client as LarkWSClient
    from lark_oapi import Client as LarkClient

    from .orchestrator import get_orchestrator

    # 校验配置
    if not FEISHU_APP_ID or not FEISHU_APP_SECRET:
        print("❌ 飞书配置缺失！请在 .env 中设置:")
        print("   FEISHU_APP_ID=cli_xxxxxxxxxxxx")
        print("   FEISHU_APP_SECRET=xxxxxxxxxxxxxxxxxxxxxxxx")
        sys.exit(1)

    print("🚀 启动 LabQA-RAG 飞书长连接模式...\n")

    # 初始化 Orchestrator（含索引和 LLM）
    orchestrator = get_orchestrator()
    orchestrator.initialize()

    print(f"📱 飞书 App ID: {FEISHU_APP_ID[:8]}...")
    print("🔌 建立 WebSocket 连接...\n")

    # 飞书客户端（用于发送消息）
    lark_client = LarkClient.builder() \
        .app_id(FEISHU_APP_ID) \
        .app_secret(FEISHU_APP_SECRET) \
        .build()

    # 事件处理
    def on_message(event: dict):
        """处理收到的消息事件"""
        try:
            msg = event.get("message", event)
            chat_id = msg.get("chat_id", "")
            message_id = msg.get("message_id", "")
            msg_type = msg.get("msg_type", "text")

            # 只处理文本消息
            if msg_type != "text":
                return

            # 解析内容
            content_raw = msg.get("content", "{}")
            try:
                content_data = json.loads(content_raw)
                content = content_data.get("text", "")
            except json.JSONDecodeError:
                content = content_raw

            if not content:
                return

            # 清理 @机器人 前缀
            content = content.strip().lstrip("@").strip()

            if DEBUG:
                print(f"\n[Feishu] 📩 收到: {content[:100]}...")

            # 处理
            response = _handle_message(chat_id, message_id, content, orchestrator)

            if response:
                _send_message(lark_client, chat_id, response)

        except Exception as e:
            print(f"[Feishu] 事件处理异常: {e}")

    # 创建 WS 客户端
    ws_client = LarkWSClient.builder() \
        .app_id(FEISHU_APP_ID) \
        .app_secret(FEISHU_APP_SECRET) \
        .event_handler(EventDispatcherHandler.builder()
                       .register_v2("im.message.receive_v1", on_message)
                       .build()) \
        .build()

    print("✅ LabQA-RAG 飞书服务已启动（长连接，无需公网IP）")
    print("📩 在飞书群中 @机器人 即可提问\n")

    try:
        ws_client.start()
    except KeyboardInterrupt:
        print("\n👋 飞书服务已停止")
    except Exception as e:
        print(f"\n❌ 飞书服务异常: {e}")
        raise


if __name__ == "__main__":
    start()
