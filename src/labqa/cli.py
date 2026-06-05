"""
LabQA-RAG CLI — 命令行交互界面
用于本地测试和调试
"""

import sys
import os
from pathlib import Path

# 确保 src/ 在 Python path 中
sys.path.insert(0, str(Path(__file__).parent.parent))

from .config import validate, print_config, DEBUG, LLM_MODE
from .orchestrator import get_orchestrator
from .ingest import check_indexes


BANNER = r"""
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║   🧪  LabQA-RAG v2.0 — 实验室智能问答系统                     ║
║   FAISS + BM25 + RRF 混合检索 | LangChain 驱动                ║
║                                                              ║
║   类型 /help 查看帮助    /stats 系统状态    /quit 退出          ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
"""

HELP_TEXT = """
📋 LabQA-RAG 使用帮助

直接输入问题即可，系统会自动识别意图并路由到对应Agent。

🖥  设备查询示例:
   "GPU-A100-01还有空闲卡吗？"
   "自动驾驶测试车在哪？谁负责？"
   "实验室有哪些GPU服务器？"

📂 项目查询示例:
   "LLM对齐优化项目进展如何？能赶上ICML吗？"
   "王五在做什么项目？"
   "有哪些外勤项目在进行？"

📄 文档查询示例:
   "DPO论文的核心方法是什么？"
   "怎么提交代码？"
   "新人入职流程是什么？"

🔀 混合查询示例:
   "王五在忙什么？他的GPU用完了吗？"（项目+设备）

⚙️ 系统命令:
   /help     - 显示此帮助
   /stats    - 显示系统状态（索引 + 知识库）
   /reload   - 重新加载知识库和索引
   /ingest   - 重建知识库索引
   /debug    - 切换调试模式
   /quit     - 退出
"""


def main():
    """CLI 主入口"""
    print(BANNER)

    # 配置校验
    issues = validate()
    if issues:
        for issue in issues:
            print(f"⚠️  {issue}")
        print()

    print_config()

    # 初始化 Orchestrator
    print("⏳ 初始化中...\n")
    orchestrator = get_orchestrator()
    orchestrator.initialize()

    # 索引状态
    idx_status = check_indexes()
    if idx_status["faiss_exists"] and idx_status["bm25_exists"]:
        print(f"📚 混合检索已就绪: {idx_status['document_count']} 个文档")
    else:
        print("⚠️ 索引未构建！运行 /ingest 来构建 FAISS + BM25 索引")
    print()

    # 交互循环
    debug_mode = DEBUG

    while True:
        try:
            user_input = input("💬 你: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n👋 再见！")
            break

        if not user_input:
            continue

        # 系统命令
        if user_input.startswith("/"):
            cmd = user_input[1:].lower().strip()

            if cmd in ("quit", "exit"):
                print("👋 再见！")
                break
            elif cmd == "help":
                print(HELP_TEXT)
            elif cmd == "stats":
                stats = orchestrator.stats()
                print(f"\n📊 系统状态")
                print(f"   版本: {stats['version']}")
                print(f"   LLM 模式: {stats['llm_mode']}")
                print(f"   Agent: {', '.join(stats['agents'])}")
                print(f"   知识库: {stats['indexes']['document_count']} 个文档")
                print(f"   FAISS 索引: {'✅' if stats['indexes']['faiss_exists'] else '❌'}")
                print(f"   BM25 索引: {'✅' if stats['indexes']['bm25_exists'] else '❌'}")
                print()
            elif cmd == "reload":
                orchestrator.reload()
                print("✅ 索引已更新\n")
            elif cmd == "ingest":
                print("🔄 重建索引...")
                from .generator import create_embeddings
                from .ingest import build_indexes
                embed_model = create_embeddings()
                build_indexes(embed_model, force_rebuild=True)
                orchestrator.reload()
                print("✅ 索引重建完成\n")
            elif cmd == "debug":
                debug_mode = not debug_mode
                from . import config
                config.DEBUG = debug_mode
                print(f"🔍 调试模式: {'开启' if debug_mode else '关闭'}\n")
            else:
                print(f"未知命令: {user_input}\n")
            continue

        # 普通查询
        print("\n🤖 LabQA 思考中...\n")

        try:
            response = orchestrator.process(user_input)
            print(response)
        except Exception as e:
            print(f"❌ 处理出错: {e}")

        print("\n" + "─" * 60 + "\n")


if __name__ == "__main__":
    main()
