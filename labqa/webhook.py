"""
LabQA Webhook — 飞书消息接入层
桥接飞书机器人消息与 Orchestrator
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from labqa.config import (
    FEISHU_APP_ID, FEISHU_APP_SECRET, FEISHU_VERIFICATION_TOKEN,
    WEBHOOK_HOST, WEBHOOK_PORT, DEBUG,
)
from labqa.orchestrator import get_orchestrator

try:
    from flask import Flask, request, jsonify
except ImportError:
    print("⚠️ 需要安装 flask: pip install flask")
    sys.exit(1)

try:
    import requests as http_requests
except ImportError:
    print("⚠️ 需要安装 requests: pip install requests")
    sys.exit(1)


app = Flask(__name__)
orchestrator = get_orchestrator()


# ===== 飞书 API =====

def get_tenant_access_token():
    """获取飞书 tenant_access_token"""
    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    headers = {"Content-Type": "application/json"}
    data = {"app_id": FEISHU_APP_ID, "app_secret": FEISHU_APP_SECRET}
    resp = http_requests.post(url, headers=headers, json=data)
    resp.raise_for_status()
    return resp.json()["tenant_access_token"]


def send_feishu_message(chat_id: str, text: str):
    """发送飞书消息"""
    if not FEISHU_APP_ID:
        print("[Webhook] 飞书未配置，消息仅打印:")
        print(f"  → {chat_id}: {text[:200]}...")
        return

    try:
        token = get_tenant_access_token()
        url = "https://open.feishu.cn/open-apis/im/v1/messages"
        params = {"receive_id_type": "chat_id"}
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        body = {
            "receive_id": chat_id,
            "msg_type": "text",
            "content": json.dumps({"text": text}),
        }
        resp = http_requests.post(url, headers=headers, params=params, json=body)
        resp.raise_for_status()

        if DEBUG:
            print(f"[Webhook] 消息已发送: {resp.json()}")
    except Exception as e:
        print(f"[Webhook] 发送失败: {e}")


# ===== Webhook 路由 =====

@app.route("/feishu/webhook", methods=["POST"])
def feishu_webhook():
    """飞书事件订阅回调"""
    body = request.get_json()

    # URL 验证
    if body.get("type") == "url_verification":
        return jsonify({"challenge": body.get("challenge", "")})

    # Token 验证
    token = body.get("token", "")
    if FEISHU_VERIFICATION_TOKEN and token != FEISHU_VERIFICATION_TOKEN:
        return jsonify({"code": -1, "msg": "invalid token"}), 403

    # 处理事件
    event = body.get("event", {})
    if event.get("type") == "im.message.receive_v1":
        message = event.get("message", {})
        if message.get("message_type") == "text":
            content = json.loads(message.get("content", "{}"))
            text = content.get("text", "")

            # 清理 @mention
            import re
            text = text.replace("@_all", "").strip()
            text = re.sub(r'@\S+', '', text).strip()

            if text:
                chat_id = message.get("chat_id", "")
                print(f"\n[Webhook] 收到消息: {text[:100]}...")

                try:
                    response = orchestrator.process(text)
                except Exception as e:
                    response = f"⚠️ 处理出错: {e}"

                send_feishu_message(chat_id, response)

    return jsonify({"code": 0, "msg": "success"})


@app.route("/health", methods=["GET"])
def health():
    """健康检查"""
    stats = orchestrator.stats()
    return jsonify({
        "status": "ok",
        "service": "LabQA",
        "version": "1.0.0",
        "knowledge_files": stats["knowledge"]["total"],
    })


def main():
    """启动 Webhook 服务"""
    if not FEISHU_APP_ID:
        print("⚠️  飞书未配置。请设置环境变量:")
        print("   export FEISHU_APP_ID='your-app-id'")
        print("   export FEISHU_APP_SECRET='your-app-secret'")
        print("\n💡 但您仍然可以用 CLI 模式测试:")
        print("   python3 main.py cli")
        return

    print(f"""
╔══════════════════════════════════════════╗
║   🚀 LabQA Webhook 服务启动中...         ║
║   监听: {WEBHOOK_HOST}:{WEBHOOK_PORT}                     ║
║   Webhook URL: /feishu/webhook           ║
║   健康检查: /health                       ║
╚══════════════════════════════════════════╝
""")
    app.run(host=WEBHOOK_HOST, port=WEBHOOK_PORT, debug=DEBUG)


if __name__ == "__main__":
    main()
