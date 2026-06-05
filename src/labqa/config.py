"""
LabQA-RAG 配置管理
支持 Ollama 本地模式 + 云端 API 模式双轨运行
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# 加载 .env 文件
load_dotenv()

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent.parent

# 知识库目录
CONTEXT_DIR = PROJECT_ROOT / ".opencode" / "context"
DATA_DIR = PROJECT_ROOT / "data"

# 向量索引路径
FAISS_INDEX_DIR = PROJECT_ROOT / "faiss_index"
BM25_INDEX_PATH = PROJECT_ROOT / "bm25_index.pkl"

# ===== LLM 模式 =====
LLM_MODE = os.getenv("LABQA_LLM_MODE", "ollama")  # "ollama" | "cloud"

# Ollama 配置
OLLAMA_LLM_MODEL = os.getenv("OLLAMA_LLM_MODEL", "deepseek-r1:1.5b")
OLLAMA_EMBED_MODEL = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")

# 云端 API 配置
LLM_API_KEY = os.getenv(
    "LABQA_LLM_API_KEY",
    os.getenv("DEEPSEEK_API_KEY", os.getenv("OPENAI_API_KEY", ""))
)
LLM_API_BASE = os.getenv("LABQA_LLM_API_BASE", "https://api.deepseek.com")
LLM_MODEL = os.getenv("LABQA_LLM_MODEL", "deepseek-chat")
LLM_TEMPERATURE = float(os.getenv("LABQA_LLM_TEMPERATURE", "0.3"))
LLM_MAX_TOKENS = int(os.getenv("LABQA_LLM_MAX_TOKENS", "800"))

# ===== 检索参数 =====
RETRIEVE_K = int(os.getenv("RETRIEVE_K", "5"))
FUSION_K = int(os.getenv("FUSION_K", "5"))
RRF_K = int(os.getenv("RRF_K", "60"))
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", "500"))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", "50"))

# ===== 飞书配置 =====
FEISHU_APP_ID = os.getenv("FEISHU_APP_ID", "")
FEISHU_APP_SECRET = os.getenv("FEISHU_APP_SECRET", "")
FEISHU_VERIFICATION_TOKEN = os.getenv("FEISHU_VERIFICATION_TOKEN", "")

# ===== 调试 =====
DEBUG = os.getenv("LABQA_DEBUG", "false").lower() == "true"


def validate():
    """启动前校验必要配置"""
    issues = []

    if LLM_MODE not in ("ollama", "cloud"):
        issues.append(f"LABQA_LLM_MODE 无效: {LLM_MODE}（应为 ollama 或 cloud）")

    if LLM_MODE == "cloud" and not LLM_API_KEY:
        issues.append("云端模式需要设置 LABQA_LLM_API_KEY")

    if not CONTEXT_DIR.exists():
        issues.append(f"知识库目录不存在: {CONTEXT_DIR}")

    return issues


def print_config():
    """打印当前配置（不显示敏感信息）"""
    mode_label = f"🖥 本地 Ollama ({OLLAMA_LLM_MODEL})" if LLM_MODE == "ollama" else f"☁️ 云端 API ({LLM_MODEL})"

    print(f"""
╔══════════════════════════════════════════════╗
║       LabQA-RAG v2.0 配置信息                 ║
╠══════════════════════════════════════════════╣
║  LLM 模式:    {mode_label:<32} ║
║  Embedding:   {OLLAMA_EMBED_MODEL if LLM_MODE == 'ollama' else '云端 API':<32} ║
║  混合检索:    FAISS + BM25 + RRF             ║
║  知识库:      {str(CONTEXT_DIR):<32} ║
║  检索参数:    Top-{RETRIEVE_K}/路, RRF-K={RRF_K:<2}               ║
║  分块参数:    {CHUNK_SIZE}字符, 重叠{CHUNK_OVERLAP}字符              ║
║  Debug:       {str(DEBUG):<32} ║
╚══════════════════════════════════════════════╝
""")
