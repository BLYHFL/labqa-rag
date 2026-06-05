#!/usr/bin/env python3
"""
LabQA-RAG v2.0 主入口

用法:
  python3 main.py cli          # 命令行交互模式（推荐开发调试用）
  python3 main.py ask "问题"    # 单次查询
  python3 main.py feishu        # 飞书 WebSocket 长连接模式（生产用）
  python3 main.py ingest        # 构建/重建知识库索引
  python3 main.py stats         # 查看系统状态

首次使用:
  1. cp .env.example .env
  2. 编辑 .env 选择 LLM 模式（Ollama 本地 / 云端 API）
  3. python3 main.py ingest     # 构建 FAISS + BM25 索引
  4. python3 main.py cli        # 开始交互问答
"""

import sys
import os
from pathlib import Path

# 将 src/ 加入 Python path
sys.path.insert(0, str(Path(__file__).parent / "src"))

# 加载 .env 文件（shell 环境变量优先级更高）
env_file = Path(__file__).parent / ".env"
if env_file.exists():
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        # 手写 .env 加载器
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, value = line.partition("=")
                    key = key.strip()
                    if key not in os.environ:
                        os.environ[key] = value.strip().strip('"').strip("'")

from labqa.config import validate, print_config, DEBUG, LLM_MODE


def mode_cli():
    """CLI 交互模式"""
    from labqa.cli import main as cli_main
    cli_main()


def mode_ingest():
    """知识库入库模式"""
    from labqa.ingest import main as ingest_main
    ingest_main()


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
        if any("API_KEY" in i for i in issues) and LLM_MODE == "cloud":
            print("\n💡 提示: 切换为 Ollama 本地模式无需 API Key")
            print("   在 .env 中设置 LABQA_LLM_MODE=ollama")
            sys.exit(1)

    print_config()

    from labqa.orchestrator import get_orchestrator
    orchestrator = get_orchestrator()
    orchestrator.initialize()

    print(f"\n💬 问题: {query}\n")
    print("🤖 LabQA 思考中...\n")

    try:
        response = orchestrator.process(query)
        print(response)
    except Exception as e:
        print(f"❌ 出错: {e}")


def mode_feishu():
    """飞书长连接模式"""
    from labqa.feishu_ws import start
    start()


def mode_stats():
    """系统状态"""
    from labqa.ingest import check_indexes
    status = check_indexes()

    print("📊 LabQA-RAG v2.0 系统状态\n")
    print(f"   LLM 模式:     {LLM_MODE}")
    print(f"   知识库目录:    {'✅ 存在' if status['context_exists'] else '❌ 不存在'}")
    print(f"   文档数量:      {status['document_count']}")
    print(f"   FAISS 索引:   {'✅ 已构建' if status['faiss_exists'] else '❌ 未构建（运行 python3 main.py ingest）'}")
    print(f"   BM25 索引:    {'✅ 已构建' if status['bm25_exists'] else '❌ 未构建'}")

    if not (status["faiss_exists"] and status["bm25_exists"]):
        print("\n💡 运行以下命令构建索引:")
        print("   python3 main.py ingest")


def main():
    if len(sys.argv) < 2:
        print("LabQA-RAG v2.0 — 实验室智能问答系统")
        print("FAISS + BM25 + RRF 混合检索 | LangChain 驱动\n")
        print("用法:")
        print("  python3 main.py cli         命令行交互模式")
        print("  python3 main.py ask \"问题\"   单次查询")
        print("  python3 main.py feishu       飞书长连接模式（无需公网IP）")
        print("  python3 main.py ingest       构建知识库索引")
        print("  python3 main.py stats        查看系统状态")
        print("\n首次使用:")
        print("  1. cp .env.example .env")
        print("  2. 编辑 .env 选择 LLM 模式")
        print("  3. python3 main.py ingest")
        print("  4. python3 main.py cli")
        return

    cmd = sys.argv[1].lower()

    if cmd == "cli":
        mode_cli()
    elif cmd in ("feishu", "webhook"):
        mode_feishu()
    elif cmd == "ask":
        mode_ask()
    elif cmd == "ingest":
        mode_ingest()
    elif cmd == "stats":
        mode_stats()
    else:
        print(f"未知命令: {cmd}")
        print("可用命令: cli, ask, feishu, ingest, stats")


if __name__ == "__main__":
    main()
