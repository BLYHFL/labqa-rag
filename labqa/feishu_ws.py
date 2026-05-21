"""
LabQA 飞书长连接模式（WebSocket）
基于 lark-oapi SDK，无需公网IP/域名
"""

import sys
import json
import logging
import re
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import lark_oapi as lark

from labqa.config import FEISHU_APP_ID, FEISHU_APP_SECRET, DEBUG
from labqa.orchestrator import get_orchestrator

logging.basicConfig(
    level=logging.DEBUG,
    format="[FeishuWS] %(levelname)s %(message)s",
)
logger = logging.getLogger("labqa.feishu")
logger.setLevel(logging.DEBUG)

orchestrator = get_orchestrator()

# 消息去重缓存
# 规则1: 同一 message_id 不重复处理（飞书3秒超时重推）
# 规则2: 同一 chat_id + 相同内容 + 30秒内 → 不重复处理（防止重复事件）
_processed_ids: set = set()
_content_cache: dict = {}  # {chat_id: (text_hash, timestamp)}


def _is_duplicate(msg_id: str, chat_id: str, text: str) -> bool:
    """双重去重：message_id + 内容时间窗口"""
    import time, hashlib

    # 规则1: message_id 去重
    if msg_id in _processed_ids:
        logger.info(f"[去重-ID] 跳过: {msg_id}")
        return True
    _processed_ids.add(msg_id)

    # 规则2: 内容去重（同一群，相同内容，30秒内）
    text_hash = hashlib.md5(text.encode()).hexdigest()
    now = time.time()
    key = f"{chat_id}:{text_hash}"
    if key in _content_cache:
        last_time = _content_cache[key]
        if now - last_time < 30:
            logger.info(f"[去重-内容] 30秒内重复内容，跳过: {text[:30]}...")
            return True
    _content_cache[key] = now

    # 清理过期缓存
    expired = [k for k, v in _content_cache.items() if now - v > 60]
    for k in expired:
        del _content_cache[k]

    return False


def handle_message(data: lark.im.v1.P2ImMessageReceiveV1) -> None:
    """处理接收消息事件"""
    event = data.event
    message = event.message

    # 1. 解析消息
    try:
        content = json.loads(message.content)
    except (json.JSONDecodeError, TypeError):
        return

    text = content.get("text", "").strip()
    if not text:
        return

    # 清理 @mention
    text = re.sub(r'@\S+', '', text).strip()
    if not text:
        return

    chat_id = message.chat_id
    msg_id = message.message_id

    # 2. 双重去重（message_id + 内容时间窗口）
    if _is_duplicate(msg_id, chat_id, text):
        return

    # 3. 只处理文本消息
    if message.message_type != "text":
        return

    logger.info(f"[问题] {text[:80]} (msg={msg_id})")

    # 5. 调用 LabQA
    try:
        answer = orchestrator.process(text)
    except Exception as e:
        answer = f"⚠️ 处理出错: {e}"
        logger.error(f"Orchestrator 错误: {e}", exc_info=True)

    logger.info(f"[回答] {answer[:100]}...")

    # 6. 发送回复
    send_text_message(chat_id, answer)


def send_text_message(chat_id: str, text: str) -> None:
    """发送飞书文本消息"""
    try:
        client = lark.Client.builder() \
            .app_id(FEISHU_APP_ID) \
            .app_secret(FEISHU_APP_SECRET) \
            .build()

        req = lark.api.im.v1.CreateMessageRequest.builder() \
            .receive_id_type("chat_id") \
            .request_body(
                lark.api.im.v1.CreateMessageRequestBody.builder()
                .receive_id(chat_id)
                .msg_type("text")
                .content(json.dumps({"text": text}))
                .build()
            ).build()

        resp = client.im.v1.message.create(req)

        if not resp.success():
            logger.error(f"发送失败: code={resp.code} msg={resp.msg}")
        else:
            logger.info(f"已发送: {resp.data.message_id}")

    except Exception as e:
        logger.error(f"发送异常: {e}", exc_info=True)


def start():
    """启动飞书长连接客户端"""
    if not FEISHU_APP_ID or not FEISHU_APP_SECRET:
        print("❌ 飞书未配置，请在 .env 中设置 FEISHU_APP_ID 和 FEISHU_APP_SECRET")
        sys.exit(1)

    print(f"""
╔══════════════════════════════════════════════╗
║   🚀 LabQA 飞书长连接模式                     ║
║   App ID: {FEISHU_APP_ID[:20]}...                          ║
║   模式: WebSocket 长连接，无需公网IP            ║
╚══════════════════════════════════════════════╝
""")

    # 只注册 v2.0 事件（不注册 v1.0，避免重复触发）
    event_handler = (
        lark.EventDispatcherHandler.builder("", "")
        .register_p2_im_message_receive_v1(handle_message)
        .build()
    )

    client = lark.ws.Client(
        FEISHU_APP_ID,
        FEISHU_APP_SECRET,
        event_handler=event_handler,
        log_level=lark.LogLevel.INFO,
    )

    client.start()


if __name__ == "__main__":
    start()
