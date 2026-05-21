"""
LabQA 配置管理
从环境变量读取所有配置，支持 .env 文件
"""

import os
from pathlib import Path

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent

# 上下文文件目录
CONTEXT_DIR = PROJECT_ROOT / ".opencode" / "context"

# Agent 定义目录
AGENT_DIR = PROJECT_ROOT / ".opencode" / "agent"

# ------- LLM 配置 -------
LLM_PROVIDER = os.getenv("LABQA_LLM_PROVIDER", "deepseek")  # deepseek | openai | custom

LLM_API_KEY = os.getenv("LABQA_LLM_API_KEY", os.getenv("DEEPSEEK_API_KEY", ""))
LLM_API_BASE = os.getenv("LABQA_LLM_API_BASE", "https://api.deepseek.com/v1")
LLM_MODEL = os.getenv("LABQA_LLM_MODEL", "deepseek-chat")

# 备用：也可以从 OPENAI_API_KEY 等环境变量读取
if not LLM_API_KEY:
    if LLM_PROVIDER == "openai":
        LLM_API_KEY = os.getenv("OPENAI_API_KEY", "")
    elif LLM_PROVIDER == "custom":
        LLM_API_KEY = os.getenv("CUSTOM_API_KEY", "")

# LLM 参数
LLM_TEMPERATURE = float(os.getenv("LABQA_LLM_TEMPERATURE", "0.3"))
LLM_MAX_TOKENS = int(os.getenv("LABQA_LLM_MAX_TOKENS", "800"))

# ------- 飞书配置 -------
FEISHU_APP_ID = os.getenv("FEISHU_APP_ID", "")
FEISHU_APP_SECRET = os.getenv("FEISHU_APP_SECRET", "")
FEISHU_VERIFICATION_TOKEN = os.getenv("FEISHU_VERIFICATION_TOKEN", "")

# ------- 服务配置 -------
WEBHOOK_HOST = os.getenv("LABQA_HOST", "0.0.0.0")
WEBHOOK_PORT = int(os.getenv("LABQA_PORT", "8080"))

# ------- 调试 -------
DEBUG = os.getenv("LABQA_DEBUG", "false").lower() == "true"


def validate():
    """启动前校验必要配置"""
    issues = []

    if not LLM_API_KEY:
        issues.append("LABQA_LLM_API_KEY 或 DEEPSEEK_API_KEY 未设置")

    if not CONTEXT_DIR.exists():
        issues.append(f"知识库目录不存在: {CONTEXT_DIR}")

    return issues


def print_config():
    """打印当前配置（不显示敏感信息）"""
    print(f"""
╔══════════════════════════════════════════╗
║         LabQA 配置信息                    ║
╠══════════════════════════════════════════╣
║  LLM Provider:  {LLM_PROVIDER:<25} ║
║  LLM Model:     {LLM_MODEL:<25} ║
║  LLM Base URL:  {LLM_API_BASE:<25} ║
║  Context Dir:   {str(CONTEXT_DIR):<25} ║
║  Debug:         {str(DEBUG):<25} ║
╚══════════════════════════════════════════╝
""")
