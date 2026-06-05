# LabQA-RAG：基于混合检索的实验室智能问答系统

[![Python 3.9+](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://www.python.org/)
[![LangChain](https://img.shields.io/badge/LangChain-0.3+-green.svg)](https://www.langchain.com/)
[![FAISS](https://img.shields.io/badge/FAISS-1.8+-orange.svg)](https://github.com/facebookresearch/faiss)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

基于 **LangChain + FAISS + BM25 + RRF 混合检索** 的 RAG 知识库问答系统，专为实验室场景设计。

## 架构总览

```
用户提问 → 意图路由 → Agent → FAISS稠密检索 + BM25稀疏检索
                                    ↓
                              RRF 融合排名 → Top-K文档
                                    ↓
                              Prompt构建 → LLM生成 → 回答
```

### 核心特性

- **混合检索**：FAISS 向量检索（语义匹配）+ BM25 稀疏检索（关键词匹配）+ RRF 融合
- **双轨 LLM**：支持 Ollama 本地模型（免费）和云端 API（DeepSeek/OpenAI）
- **Multi-Agent**：设备查询 / 项目查询 / 文档查询 三大 Agent 自动路由
- **飞书集成**：WebSocket 长连接模式，无需公网 IP
- **中文优化**：jieba 分词 + RecursiveCharacterTextSplitter 中文分块

## 快速开始

```bash
# 1. 安装依赖
uv venv --python 3.9
source .venv/bin/activate
uv pip install -e ".[dev]"

# 2. 安装 Ollama（可选，用于本地模式）
# 从 https://ollama.com 下载安装
ollama pull deepseek-r1:1.5b
ollama pull nomic-embed-text

# 3. 配置环境变量
cp .env.example .env
# 编辑 .env，选择 LLM 模式

# 4. 构建知识库索引
python3 main.py ingest

# 5. 开始使用
python3 main.py cli          # 命令行交互
python3 main.py ask "问题"    # 单次查询
python3 main.py feishu        # 飞书长连接
```

## 项目结构

```
labqa-rag/
├── main.py                     # 统一入口
├── pyproject.toml              # uv 依赖管理
├── src/
│   └── labqa/
│       ├── ingest.py           # 文档加载 + FAISS/BM25 索引构建
│       ├── retriever.py        # 混合检索（FAISS + BM25 + RRF）
│       ├── generator.py        # LLM 适配器（Ollama + 云端API）
│       ├── prompts.py          # Prompt 模板
│       ├── router.py           # 意图识别与路由引擎
│       ├── orchestrator.py     # 主调度器
│       ├── cli.py              # 命令行交互
│       ├── feishu_ws.py        # 飞书 WebSocket 集成
│       ├── config.py           # 配置管理
│       └── agents/             # Agent 层
│           ├── base.py
│           ├── device_agent.py
│           ├── project_agent.py
│           └── knowledge_agent.py
├── tests/
│   └── test_main.py
├── data/                       # 知识库原始文档
├── .opencode/context/          # 知识库 Markdown 文件
├── faiss_index/                # FAISS 索引（运行时生成）
└── bm25_index.pkl              # BM25 索引（运行时生成）
```

## 技术栈

| 组件 | 用途 | 选型 |
|------|------|------|
| LLM | 生成答案 | Ollama + DeepSeek-R1 1.5B / 云端 API |
| Embedding | 文本向量化 | Ollama + nomic-embed-text / OpenAI |
| 稠密检索 | 语义相似度 | FAISS |
| 稀疏检索 | 关键词匹配 | BM25（rank-bm25）|
| 融合算法 | 多路合并 | RRF（倒数排名融合）|
| 框架 | 流程串联 | LangChain |
| 包管理 | 依赖管理 | uv + pyproject.toml |

## 使用方式

### CLI 交互模式

```bash
python3 main.py cli
```

### 单次查询

```bash
python3 main.py ask "GPU服务器还有空闲卡吗？"
```

### 飞书机器人

```bash
# .env 配置飞书 App ID 和 Secret
python3 main.py feishu
```

### 索引管理

```bash
python3 main.py ingest      # 构建/重建索引
python3 main.py stats       # 查看索引状态
```

## 扩展方向

- 接入更多文档源：PDF / Word / Notion / 数据库
- 多轮对话支持（聊天历史 + 追问）
- Web UI（Streamlit / Gradio）
- Re-Ranking 精排模型
- LLM 路由（替代关键词路由）

## License

MIT
