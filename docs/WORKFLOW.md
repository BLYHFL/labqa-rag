# LabQA-RAG 问答流程详解

## 全文概览

从用户提问到最终回答，系统经过 **4 个核心环节**：

```
用户提问 → [1.Router 意图路由] → [2.Agent 分发] → [3.混合检索] → [4.LLM 生成回答]
```

---

## 一、整体架构

```
                          ┌──────────────────────┐
                          │   用户提问             │
                          │   "王五的GPU用完了吗?"  │
                          └──────────┬───────────┘
                                     │
                          ┌──────────▼───────────┐
                          │   Router 意图识别      │
                          │   ┌───────────────┐   │
                          │   │ 关键词提取+打分 │   │
                          │   │ Device: ████░░ │ 3 │
                          │   │ Project:██████ │ 6 │
                          │   │ Knowl:  ██░░░░ │ 1 │
                          │   └───────────────┘   │
                          │   主意图: Project      │
                          │   次要: Device (混合)   │
                          └──────────┬───────────┘
                                     │
                    ┌────────────────┼────────────────┐
                    │                                  │
         ┌──────────▼──────────┐          ┌──────────▼──────────┐
         │  ProjectAgent        │          │  DeviceAgent         │
         │  category="projects" │          │  category="devices"  │
         │  prompt=项目专用      │          │  prompt=设备专用      │
         └──────────┬──────────┘          └──────────┬──────────┘
                    │                                  │
         ┌──────────▼──────────┐          ┌──────────▼──────────┐
         │   混合检索           │          │   混合检索           │
         │  ┌──FAISS 语义────┐ │          │  ┌──FAISS 语义────┐ │
         │  │ 向量相似度 Top-5│ │          │  │ 向量相似度 Top-5│ │
         │  └────────────────┘ │          │  └────────────────┘ │
         │  ┌──BM25 关键词───┐ │          │  ┌──BM25 关键词───┐ │
         │  │ jieba分词 Top-5│ │          │  │ jieba分词 Top-5│ │
         │  └────────────────┘ │          │  └────────────────┘ │
         │         ↓            │          │         ↓            │
         │  ┌──RRF 融合──────┐ │          │  ┌──RRF 融合──────┐ │
         │  │ 1/(60+rank)累加│ │          │  │ 1/(60+rank)累加│ │
         │  │ 综合排名 Top-5 │ │          │  │ 综合排名 Top-5 │ │
         │  └────────────────┘ │          │  └────────────────┘ │
         └──────────┬──────────┘          └──────────┬──────────┘
                    │                                  │
         ┌──────────▼──────────┐          ┌──────────▼──────────┐
         │   Prompt 模板        │          │   Prompt 模板        │
         │   "你是项目管理..."   │          │   "你是设备管理..."   │
         │   + 检索到的文档块    │          │   + 检索到的文档块    │
         └──────────┬──────────┘          └──────────┬──────────┘
                    │                                  │
         ┌──────────▼──────────┐          ┌──────────▼──────────┐
         │   LLM 生成           │          │   LLM 生成           │
         │   Ollama/云端API     │          │   Ollama/云端API     │
         └──────────┬──────────┘          └──────────┬──────────┘
                    │                                  │
                    └────────────┬─────────────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │   Orchestrator 合并结果  │
                    │   主回答 + 次要回答       │
                    └────────────┬────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │   最终回答返回用户        │
                    └─────────────────────────┘
```

---

## 二、三大 Agent 关键词库

### DeviceAgent 关键词库 (`router.py`)

```python
DEVICE_KEYWORDS = [
    # 设备类型
    "设备", "服务器", "gpu", "cpu", "内存", "硬盘", "网络",
    "机柜", "仪器", "机器", "ip", "显卡", "算力",
    # GPU 型号
    "a100", "h100", "v100", "4090", "h800", "a800",
    # 状态
    "空闲", "谁在用", "在哪", "坏了", "维修", "故障",
    "使用", "占用", "重启", "登录", "ssh",
    # 存储
    "nas", "存储", "数据盘", "硬盘",
    # 外勤设备
    "测试车", "激光雷达", "采集套件", "传感器",
    "交换机", "工作站", "工位",
]
```

### ProjectAgent 关键词库 (`router.py`)

```python
PROJECT_KEYWORDS = [
    # 项目管理
    "项目", "进度", "里程碑", "需求", "负责人", "排期",
    "ddl", "deadline", "交付", "上线", "测试", "外勤",
    "实验", "论文项目",
    # 会议/期刊
    "icml", "neurips", "cvpr", "iccv", "eccv", "iclr", "aaai",
    "截稿", "投稿", "会议",
    # 人员
    "谁负责", "谁在做", "在做什么",
    # 技术方向
    "llm", "rlhf", "dpo", "对齐", "自动驾驶", "感知",
    "融合", "小样本", "预研", "探索",
    # 状态
    "进展", "赶得上", "来得及",
]
```

### KnowledgeAgent 关键词库 (`router.py`)

```python
KNOWLEDGE_KEYWORDS = [
    # 文档类型
    "论文", "文档", "调研", "规范", "流程", "教程", "指南",
    "怎么做", "怎么配置", "怎么申请", "怎么提交",
    "规范是什么", "要求是什么",
    # 流程
    "入职", "离职", "新人", "代码规范", "提交规范",
    "权限", "账号", "密码",
    # 论文相关
    "论文笔记", "论文讲了什么", "论文内容", "论文总结",
    "方法对比", "技术分析", "核心方法",
    # 技术名
    "dpo", "rlhf", "transformer", "attention", "ppo", "kto", "sft",
    # 比较
    "区别", "对比", "哪个更好", "优缺点",
]
```

---

## 三、Router 打分机制 (`router.py`)

### 分词

```python
def extract_keywords(text: str) -> List[str]:
    # 中文：按常见分隔切分
    # 英文：按空格和标点切分
    # 特殊实体：识别型号如 A100, H100, GPU-A100-01
```

### 评分规则

```python
def _score_intent(text, keywords, intent_keywords) -> int:
    score = 0
    for kw in intent_keywords:
        if kw in text.lower():
            if len(kw) <= 3:      # 短关键词: +1分
                score += 1
            else:                  # 长关键词: +2分
                score += 2
        if kw in keywords:         # 精确分词匹配: +1分
            score += 1
    return score
```

### 混合意图判定

```python
# 次要意图需满足:
# 1. 分数 > 0
# 2. 分数 >= 主意图分数的 50%
secondary = [k for k, v in scores.items()
             if k != primary and v > 0 and v >= max_score * 0.5]
```

---

## 四、完整示例走读

### 示例 1：纯设备查询 — "GPU-A100-01 还有空闲卡吗？"

#### Step 1: Router 意图识别

```
输入: "GPU-A100-01 还有空闲卡吗？"

[Router] 分词: ["gpu", "a100", "空闲", "卡", "gpu-a100-01"]

打分:
  DEVICE_KEYWORDS:
    "gpu" 在文本中 → +2 (长关键词, >3字符)
    "gpu" 在分词中 → +1 (精确匹配)
    "a100" 在文本中 → +2
    "空闲" 在文本中 → +1 (短关键词, ≤3字符)
    → 总计: 6分

  PROJECT_KEYWORDS:
    → 0分 (无一命中)

  KNOWLEDGE_KEYWORDS:
    → 0分 (无一命中)

[Router] 主意图: device (置信度: 1.00)
[Router] 匹配词: ['gpu', 'a100', '空闲']
```

#### Step 2: Agent 分发

```python
# Orchestrator 根据路由决策选择 Agent
agent = self.agents["Device-Agent"]

# DeviceAgent 配置:
#   category = "devices"   → 只搜索 context/devices/ 目录
#   agent_type = "device"  → 使用设备专用 Prompt
```

#### Step 3: 混合检索

**FAISS 稠密检索（语义匹配）：**

```
查询向量: embed("GPU-A100-01 还有空闲卡吗？")
    ↓ 在 devices/ 目录的向量索引中搜索
命中 Top-5:
  1. devices/GPU-A100-01.md (score: 0.92)
  2. devices/GPU-H100-01.md (score: 0.78)
  3. devices/设备总览.md      (score: 0.65)
  4. devices/GPU-A100-01.md (score: 0.61) # 另一个分块
  5. devices/GPU-H100-01.md (score: 0.55) # 另一个分块
```

**BM25 稀疏检索（关键词匹配）：**

```
查询分词: jieba.cut("GPU-A100-01 还有空闲卡吗")
         → ["gpu", "a100", "空闲", "卡"]

BM25 倒排索引匹配 Top-5:
  1. devices/GPU-A100-01.md (score: 12.5) # "GPU-A100-01"精确命中
  2. devices/GPU-H100-01.md (score: 5.2)
  3. devices/设备总览.md     (score: 3.1)
```

**RRF 融合：**

```
文档 "devices/GPU-A100-01.md":
  FAISS 排名第1: 1/(60+1) = 0.01639
  BM25  排名第1: 1/(60+1) = 0.01639
  RRF 总分: 0.03279 ← 最高

文档 "devices/设备总览.md":
  FAISS 排名第3: 1/(60+3) = 0.01587
  BM25  排名第3: 1/(60+3) = 0.01587
  RRF 总分: 0.03174

最终排序:
  [1] GPU-A100-01.md (RRF: 0.03279) ← 两路都是第一
  [2] GPU-H100-01.md (RRF: 0.027...)
  [3] 设备总览.md      (RRF: 0.03174)
```

#### Step 4: LLM 生成

检索到的文档块拼接为上下文，注入设备专用 Prompt：

```markdown
你是实验室设备管理员。基于设备信息回答问题，简洁直接。

## 设备信息
[devices/GPU-A100-01.md]
GPU-A100-01 | 机柜A3 | 4卡 NVIDIA A100 80GB
当前状态: 3卡占用，1卡空闲
空闲卡: GPU-3
负责人: 张三
采购日期: 2024-03
...

---
问题: GPU-A100-01 还有空闲卡吗？

回答格式:
- 单设备: 名称 | 位置 | 状态 | 负责人，一行搞定
- 空闲/占用情况用简表
- 禁止开场白、禁止"好的"、禁止末尾总结
- 引用来源放最后一行

回答:
```

LLM 返回：

```
GPU-A100-01 | 机柜A3 | 1/4卡空闲 | 张三

| 卡号   | 状态   | 使用者 |
|--------|--------|--------|
| GPU-1  | 🔴占用 | 李四   |
| GPU-2  | 🔴占用 | 王五   |
| GPU-3  | 🟢空闲 | -      |
| GPU-4  | 🔴占用 | 赵六   |

📎 来源: devices/GPU-A100-01.md
```

---

### 示例 2：纯文档查询 — "DPO 论文的核心方法是什么？"

```
输入: "DPO 论文的核心方法是什么？"

[Router] 分词: ["dpo", "论文", "核心", "方法"]

打分:
  DEVICE_KEYWORDS:    0分
  PROJECT_KEYWORDS:   "dpo"命中 → +3 (文本2+分词1)  = 3分
  KNOWLEDGE_KEYWORDS: "论文"命中 → +2 (长词)
                      "dpo"命中  → +3
                      "方法对比" → +1
                      → 总计: 6分

[Router] 主意图: knowledge (置信度: 1.00)
    ↓
[Orchestrator] → KnowledgeAgent
    ↓
[KnowledgeAgent] category=None → 搜索全部目录
    ↓
[混合检索] knowledge/论文笔记/ + guides/ 全部纳入搜索范围
    ↓
检索到: knowledge/论文笔记/DPO论文总结.md
    ↓
[LLM Prompt] "你是实验室知识管理员..."
    ↓
回答: "DPO (Direct Preference Optimization) 通过直接优化策略网络
       来拟合人类偏好，避免了RLHF中训练奖励模型和PPO强化学习的
       复杂流程。核心方法为: 将偏好数据转化为成对比较损失函数..."
```

---

### 示例 3：混合意图 — "王五在忙什么？他的 GPU 用完了吗？"

这是最体现 Multi-Agent 架构价值的场景——**一个问题同时命中两个领域**：

```
输入: "王五在忙什么？他的 GPU 用完了吗？"

[Router] 分词: ["王五", "忙什么", "gpu", "用完了"]

打分:
  DEVICE_KEYWORDS:
    "gpu" 在文本中  → +2
    "gpu" 在分词中  → +1
    "使用"(隐含)    → 0
    → 总计: 3分

  PROJECT_KEYWORDS:
    "王五" 在文本中  → +2
    "王五" 在分词中  → +1
    "谁在做"接近     → +1
    "在做什么"命中   → +2
    → 总计: 6分

  KNOWLEDGE_KEYWORDS: 1分

[Router] 主意图: project (6分)
[Router] 次要意图: [device]  ← 3分 ≥ 6×0.5=3，触发混合意图
```

**Orchestrator 处理混合意图：**

```python
# 主 Agent: ProjectAgent
primary_response = project_agent.answer("王五在忙什么？他的 GPU 用完了吗？")
# → 检索 projects/ 目录
# → "LLM对齐优化项目 | 王五 | 工程实现 | 🔴紧急 | ICML 6/15截稿"

# 次要 Agent: DeviceAgent
secondary_response = device_agent.answer("王五在忙什么？他的 GPU 用完了吗？")
# → 检索 devices/ 目录
# → "GPU-A100-01 | 王五占用2卡 | 0卡空闲"

# 合并结果
final_response = f"""{primary_response}

---

📎 设备信息:
{secondary_response}
"""
```

最终返回：

```
王五 | LLM对齐优化项目 | 工程实现 | 🔴紧急
关键节点: 改进方法验证中，ICML 6/15截稿
风险: GPU算力紧张，可能需要排队

---

📎 设备信息:
GPU-A100-01 | 王五占用 GPU-1, GPU-2 | 0卡空闲
💡 建议: 可申请夜间时段或使用 GPU-H100-01（当前2/4卡空闲）
```

---

## 五、关键设计点

### 1. Router 是"轻量级前端"，Agent 是"专业后端"

| 层级 | 功能 | 成本 |
|------|------|------|
| Router | 关键词匹配，快速决定谁来处理 | 零成本（纯字符串匹配） |
| Agent | 向量检索 + LLM 生成，真正回答问题 | 需要 Embedding + LLM 推理 |

### 2. 混合意图是自动发现的

不需要用户说"帮我同时查王五的项目和设备"，系统通过关键词重叠自动判定 `MIXED` 场景：

```python
# 判定条件: 次要意图分数 ≥ 主意图分数的 50%
if v > 0 and v >= max_score * 0.5:
    secondary.append(k)
```

### 3. Agent 的 category 过滤保证精准度

```
DeviceAgent.category = "devices"    → 只搜 context/devices/
ProjectAgent.category = "projects"  → 只搜 context/projects/
KnowledgeAgent.category = None      → 搜索全部目录
```

DeviceAgent 只搜 `devices/` 目录，不会因为"GPU"这个词误检索到论文笔记中关于 GPU 的讨论。KnowledgeAgent 搜索全部，因为用户可能要同时查论文和流程指南。

### 4. FAISS + BM25 互补

| 检索方式 | 擅长 | 弱点 |
|----------|------|------|
| FAISS（向量） | "GPU 服务器"和"显卡机器"之间的语义关联 | 专有名词、精确型号容易漏 |
| BM25（关键词） | "A100""H100"等精确型号不遗漏 | 不理解同义词和语义 |

RRF 融合让两者互补：语义相关的不会漏，精确匹配的不会丢。

### 5. 索引持久化

```
首次运行 python main.py ingest:
  📚 加载知识库文档...
  已加载 8 个文档，切分为 32 个块
  🔍 构建 FAISS 向量索引 (32 个文档块)...
  🔍 构建 BM25 索引 (32 个文档块)...
  ✅ 所有索引就绪

之后每次启动:
  📦 检测到已有 FAISS 索引，加载中...
  📦 检测到已有 BM25 索引，加载中...
  ✅ 索引加载完成（无需重复构建）
```

---

## 六、文件索引

| 文件 | 职责 |
|------|------|
| `src/labqa/router.py` | 意图识别：关键词提取、三路打分、混合意图判定 |
| `src/labqa/agents/base.py` | Agent 基类：`search_context()` + `answer()` |
| `src/labqa/agents/device_agent.py` | DeviceAgent: category="devices" |
| `src/labqa/agents/project_agent.py` | ProjectAgent: category="projects" |
| `src/labqa/agents/knowledge_agent.py` | KnowledgeAgent: category=None（全量搜索） |
| `src/labqa/orchestrator.py` | 主调度器：路由 → Agent → 合并结果 |
| `src/labqa/retriever.py` | 混合检索：FAISS + BM25 + RRF |
| `src/labqa/generator.py` | LLM 生成：OllamaChat + ChatOpenAI + Prompt |
| `src/labqa/prompts.py` | 各 Agent 专用 Prompt 模板 |
| `src/labqa/ingest.py` | 知识库入库：文档加载 → 分块 → 建索引 |

---

## 七、快速使用

```bash
# 构建知识库索引（首次运行）
python3 main.py ingest

# 命令行交互
python3 main.py cli

# 单次查询
python3 main.py ask "GPU-A100-01 还有空闲卡吗？"

# 飞书机器人
python3 main.py feishu
```
