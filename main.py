#!/usr/bin/env python3
"""
LabQA 主入口
用法:
  python3 main.py cli        # 命令行交互模式
  python3 main.py webhook    # 飞书 Webhook 服务
  python3 main.py ask "问题"  # 单次查询
"""

import sys
import os
from pathlib import Path

# 加载 .env 文件（如果存在），shell环境变量优先级更高
env_file = Path(__file__).parent / ".env"
if env_file.exists():
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                key = key.strip()
                if key not in os.environ:  # shell环境变量优先
                    os.environ[key] = value.strip().strip('"').strip("'")

from labqa.config import validate, print_config, DEBUG


def mode_cli():
    """CLI 交互模式"""
    from labqa.cli import main as cli_main
    cli_main()


def mode_webhook():
    """飞书 Webhook 模式"""
    from labqa.webhook import main as webhook_main
    webhook_main()


def mode_ask():
    """单次查询模式"""
    if len(sys.argv) < 3:
        print("用法: python3 main.py ask \"你的问题\"")
        sys.exit(1)

    query = sys.argv[2]
    issues = validate()
    if issues:
        for issue in issues:
            print(f"⚠️  {issue}")
        sys.exit(1)

    print_config()

    from labqa.orchestrator import get_orchestrator
    orchestrator = get_orchestrator()

    print(f"\n💬 问题: {query}\n")
    print("🤖 LabQA 思考中...\n")

    try:
        response = orchestrator.process(query)
        print(response)
    except Exception as e:
        print(f"❌ 出错: {e}")


def mode_feishu():
    """飞书长连接模式（WebSocket，无需公网IP）"""
    from labqa.feishu_ws import start
    start()


def main():
    if len(sys.argv) < 2:
        print("LabQA v1.0 — 实验室智能问答系统\n")
        print("用法:")
        print("  python3 main.py cli        命令行交互模式")
        print("  python3 main.py feishu     飞书长连接模式（无需公网IP）")
        print("  python3 main.py ask \"问题\"  单次查询")
        print("\n首次使用请设置环境变量:")
        print("  cp .env.example .env")
        print("  编辑 .env 填入 LLM API Key")
        print("\n飞书接入:")
        print("  1. .env 填入 FEISHU_APP_ID 和 FEISHU_APP_SECRET")
        print("  2. 飞书后台选择「使用长连接接收事件」")
        print("  3. python3 main.py feishu")
        return

    cmd = sys.argv[1].lower()

    if cmd == "cli":
        mode_cli()
    elif cmd == "webhook" or cmd == "feishu":
        mode_feishu()
    elif cmd == "ask":
        mode_ask()
    else:
        print(f"未知命令: {cmd}")
        print("可用命令: cli, feishu, ask")


if __name__ == "__main__":
    main()
