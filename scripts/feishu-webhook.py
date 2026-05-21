#!/usr/bin/env python3
"""
LabQA 飞书 Webhook 处理器
接收飞书消息事件，路由到 Lab-Orchestrator 处理

使用方式:
  python3 feishu-webhook.py

前置条件:
  - 设置环境变量: FEISHU_APP_ID, FEISHU_APP_SECRET
  - 飞书应用已配置事件订阅 URL 指向本服务

依赖: pip install flask requests
"""

import json
import hashlib
import time
import requests
import os
from flask import Flask, request, jsonify

app = Flask(__name__)

# ===== 飞书配置 =====
FEISHU_APP_ID = os.environ.get("FEISHU_APP_ID", "")
FEISHU_APP_SECRET = os.environ.get("FEISHU_APP_SECRET", "")
FEISHU_VERIFICATION_TOKEN = os.environ.get("FEISHU_VERIFICATION_TOKEN", "")

# ===== 飞书 API =====
def get_tenant_access_token():
    """获取飞书 tenant_access_token"""
    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    headers = {"Content-Type": "application/json"}
    data = {
        "app_id": FEISHU_APP_ID,
        "app_secret": FEISHU_APP_SECRET
    }
    resp = requests.post(url, headers=headers, json=data)
    resp.raise_for_status()
    return resp.json()["tenant_access_token"]


def send_message(chat_id, content):
    """通过飞书API发送消息"""
    token = get_tenant_access_token()
    url = "https://open.feishu.cn/open-apis/im/v1/messages"
    params = {"receive_id_type": "chat_id"}
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    body = {
        "receive_id": chat_id,
        "msg_type": "interactive",
        "content": json.dumps(content)
    }
    resp = requests.post(url, headers=headers, params=params, json=body)
    resp.raise_for_status()
    return resp.json()


def send_text_message(chat_id, text):
    """发送纯文本消息"""
    token = get_tenant_access_token()
    url = "https://open.feishu.cn/open-apis/im/v1/messages"
    params = {"receive_id_type": "chat_id"}
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    body = {
        "receive_id": chat_id,
        "msg_type": "text",
        "content": json.dumps({"text": text})
    }
    resp = requests.post(url, headers=headers, params=params, json=body)
    resp.raise_for_status()
    return resp.json()


# ===== 意图识别 =====
def recognize_intent(text):
    """简单关键词匹配识别用户意图"""
    text_lower = text.lower()

    device_keywords = [
        "设备", "服务器", "gpu", "cpu", "内存", "硬盘", "网络",
        "机柜", "仪器", "机器", "ip", "显卡", "算力", "a100", "h100", "v100",
        "空闲", "谁在用", "在哪", "坏了", "维修"
    ]

    project_keywords = [
        "项目", "进度", "里程碑", "需求", "负责人", "排期",
        "ddl", "deadline", "交付", "上线", "测试", "外勤", "实验"
    ]

    knowledge_keywords = [
        "论文", "文档", "调研", "规范", "流程", "教程", "指南",
        "怎么做", "怎么配置", "规范是什么", "入职", "离职", "代码规范"
    ]

    scores = {
        "device": sum(1 for kw in device_keywords if kw in text_lower),
        "project": sum(1 for kw in project_keywords if kw in text_lower),
        "knowledge": sum(1 for kw in knowledge_keywords if kw in text_lower)
    }

    # 返回得分最高的意图
    max_score = max(scores.values())
    if max_score == 0:
        return "unknown"

    intents = [k for k, v in scores.items() if v == max_score]
    return intents[0] if len(intents) == 1 else "mixed"


# ===== LabQA 处理 =====
def process_query(text):
    """
    处理用户查询 - 这里作为桥接层
    实际处理逻辑由 Lab-Orchestrator Agent 完成
    
    当前 MVP 版本返回意图识别结果，后续接入 Agent 体系
    """
    intent = recognize_intent(text)

    if intent == "unknown":
        return {
            "title": "无法识别的问题类型",
            "content": (
                "不确定您的问题属于哪一类，能否换个方式描述？\n\n"
                "当前支持的问题类型：\n"
                "🖥  设备查询 - 如：GPU服务器在哪、A100还有空闲的吗\n"
                "📂 项目查询 - 如：XX项目进度如何、谁负责数据采集\n"
                "📄 文档查询 - 如：那篇Transformer论文讲了什么、入职流程是什么"
            )
        }

    return {
        "title": f"意图识别: {intent}",
        "content": f"已识别意图类型: {intent}\n原始问题: {text}\n\n[待接入 Agent 体系处理...]"
    }


# ===== Webhook 路由 =====
@app.route("/feishu/webhook", methods=["POST"])
def feishu_webhook():
    """飞书事件订阅回调"""
    body = request.get_json()

    # URL 验证（首次配置时飞书会发送 challenge）
    if body.get("type") == "url_verification":
        return jsonify({"challenge": body.get("challenge", "")})

    # 验证 token
    token = body.get("token", "")
    if FEISHU_VERIFICATION_TOKEN and token != FEISHU_VERIFICATION_TOKEN:
        return jsonify({"code": -1, "msg": "invalid token"}), 403

    # 处理消息事件
    event = body.get("event", {})
    event_type = event.get("type", "")

    if event_type == "im.message.receive_v1":
        message = event.get("message", {})
        message_type = message.get("message_type", "")

        # 只处理文本消息
        if message_type == "text":
            content = json.loads(message.get("content", "{}"))
            text = content.get("text", "")

            # 清理 @机器人 的 mention
            text = text.replace("@_all", "").strip()
            # 移除 @用户名 格式
            import re
            text = re.sub(r'@\S+', '', text).strip()

            if text:
                # 获取 chat_id
                chat_id = message.get("chat_id", "")

                # 处理查询
                result = process_query(text)

                # 异步回复（飞书要求3秒内响应，所以先回空然后异步发消息）
                # MVP阶段先同步回复
                if chat_id:
                    response_text = f"**{result['title']}**\n\n{result['content']}"
                    try:
                        send_text_message(chat_id, response_text)
                    except Exception as e:
                        print(f"发送消息失败: {e}")

    return jsonify({"code": 0, "msg": "success"})


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "LabQA Webhook"})


# ===== 启动 =====
if __name__ == "__main__":
    if not FEISHU_APP_ID or not FEISHU_APP_SECRET:
        print("⚠️  警告: 未设置飞书应用凭证")
        print("   请设置环境变量: FEISHU_APP_ID, FEISHU_APP_SECRET")
        print("   当前将以演示模式运行（仅意图识别，不回复飞书消息）")
        print()

    print("🚀 LabQA 飞书 Webhook 启动中...")
    print("   监听地址: http://0.0.0.0:8080")
    print("   Webhook URL: http://<your-ip>:8080/feishu/webhook")
    print()

    app.run(host="0.0.0.0", port=8080, debug=True)
