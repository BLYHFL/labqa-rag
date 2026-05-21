"""
LabQA CLI — 命令行交互界面
用于本地测试和调试
"""

import sys
from pathlib import Path

# 确保项目根目录在 Python path 中
sys.path.insert(0, str(Path(__file__).parent.parent))

from labqa.config import validate, print_config, DEBUG, LLM_API_KEY
from labqa.orchestrator import get_orchestrator


BANNER = r"""
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║   🧪  LabQA — 实验室智能问答系统  v1.0                        ║
║                                                              ║
║   类型 /help 查看帮助    /stats 系统状态    /quit 退出          ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
"""

HELP_TEXT = """
📋 LabQA 使用帮助

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
   /help    - 显示此帮助
   /stats   - 显示系统状态
   /reload  - 重新加载知识库
   /debug   - 切换调试模式
   /quit    - 退出
"""


def main():
    """CLI 主入口"""
    print(BANNER)

    # 配置校验
    issues = validate()
    if issues:
        for issue in issues:
            print(f"⚠️  {issue}")
        if any("API_KEY" in i for i in issues):
            print("\n💡 请设置环境变量后重试:")
            print("   export LABQA_LLM_API_KEY='your-api-key'")
            print("   或 export DEEPSEEK_API_KEY='your-api-key'")
            print("\n🧪 也可以先体验无LLM的知识检索模式（仅显示检索结果，不调用API）")
            choice = input("\n是否以离线模式启动？(仅知识检索，不调LLM) [y/N]: ")
            if choice.lower() != 'y':
                sys.exit(1)
            else:
                os.environ["LABQA_LLM_API_KEY"] = "offline-mode"
    else:
        print_config()

    # 预热：加载知识库
    orchestrator = get_orchestrator()
    stats = orchestrator.stats()
    print(f"\n📚 知识库已加载: {stats['knowledge']['total']} 个文件")
    for cat, count in stats['knowledge']['by_category'].items():
        print(f"   {cat}/ : {count} 个文件")
    print()

    # 交互循环
    debug_mode = DEBUG
    offline_mode = (LLM_API_KEY == "offline-mode")

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

            if cmd == "quit" or cmd == "exit":
                print("👋 再见！")
                break
            elif cmd == "help":
                print(HELP_TEXT)
            elif cmd == "stats":
                stats = orchestrator.stats()
                print(f"\n📊 系统状态")
                print(f"   Agent: {', '.join(stats['agents'])}")
                print(f"   知识库: {stats['knowledge']['total']} 个文件")
                for cat, count in stats['knowledge']['by_category'].items():
                    print(f"     {cat}: {count}")
                print()
            elif cmd == "reload":
                from labqa.context_store import get_store
                get_store().reload()
                print("✅ 知识库已重新加载\n")
            elif cmd == "debug":
                debug_mode = not debug_mode
                from labqa import config
                config.DEBUG = debug_mode
                print(f"🔍 调试模式: {'开启' if debug_mode else '关闭'}\n")
            else:
                print(f"未知命令: {user_input}\n")
            continue

        # 普通查询
        print("\n🤖 LabQA 思考中...\n")

        try:
            if offline_mode:
                # 离线模式：仅检索，不调LLM
                from labqa.router import recognize_intent
                from labqa.agents import get_agent

                decision = recognize_intent(user_input)
                print(f"🎯 意图识别: {decision.intent.value}")
                print(f"📌 路由目标: {decision.target_agent}")
                print(f"🔑 匹配关键词: {decision.matched_keywords}\n")

                agent = get_agent(decision.target_agent) if decision.target_agent in ["Device-Agent", "Project-Agent", "Knowledge-Agent"] else None
                if agent:
                    context = agent.search_context(user_input)
                    print("📚 检索到的知识库内容:\n")
                    print(context[:3000])
                    if len(context) > 3000:
                        print(f"\n... (共 {len(context)} 字符，已截断)")
                print()
            else:
                response = orchestrator.process(user_input)
                print(response)
        except Exception as e:
            print(f"❌ 处理出错: {e}")

        print("\n" + "─" * 60 + "\n")


if __name__ == "__main__":
    import os
    main()
