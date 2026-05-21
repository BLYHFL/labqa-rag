# LabQA — 实验室智能回答系统 架构设计

> **版本**: v1.0 MVP  
> **日期**: 2026-05-07  
> **状态**: 构建中

---

## 1. 系统概述

LabQA 是一个基于 .opencode Agent 体系的实验室智能问答系统，支持通过飞书机器人回答实验室成员的日常问题。系统采用 **RAG（检索增强生成）** 模式，从管理员维护的知识库中检索信息，结合 LLM 生成自然语言回答。

### 核心能力

| 场景 | 说明 | 负责 Agent |
|------|------|-----------|
| 设备/资产查询 | 某设备在哪、谁在用、维护记录 | Device-Agent |
| 项目信息查询 | 进度、人员分工、需求文档 | Project-Agent |
| 知识文档查询 | 论文笔记、技术调研、规范流程 | Knowledge-Agent |

### 实验室规模

- **人数**: ~20人
- **项目类型**: 外勤实地测试、学术论文研究、新技术探索、实验室运营管理
- **知识形态**: Word/PPT/Excel/PDF/Markdown 混合

---

## 2. 架构总览

```
┌────────────────────────────────────────────────────────────┐
│                    飞书消息入口 (@提及机器人)                  │
└─────────────────────────┬──────────────────────────────────┘
                          │ Webhook
                          ▼
┌────────────────────────────────────────────────────────────┐
│                  Lab-Orchestrator (主调度器)                 │
│         识别意图 → 选择子Agent → 整合回答                     │
└───────┬──────────────────┬──────────────────┬──────────────┘
        │ @路由             │                  │
        ▼                  ▼                  ▼
┌──────────────┐  ┌──────────────┐  ┌──────────────┐
│ Device-Agent │  │Project-Agent │  │Knowledge-Agent│
│  设备查询     │  │  项目查询     │  │  知识查询      │
└──────┬───────┘  └──────┬───────┘  └──────┬───────┘
       │                 │                 │
       └─────────┬───────┴─────────┬───────┘
                 │                 │
                 ▼                 ▼
┌────────────────────────────────────────────────────────────┐
│                    📚 统一知识库 (context/)                   │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│  │ devices/ │  │projects/ │  │knowledge/│  │ guides/  │  │
│  │ 设备知识  │  │ 项目知识  │  │ 文档知识  │  │ 流程规范  │  │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘  │
└────────────────────────────────────────────────────────────┘
                          ▲
┌────────────────────────────────────────────────────────────┐
│              🔄 文档预处理管道 (scripts/convert.sh)           │
│  Word/PPT/Excel/PDF → 统一 Markdown → 归入 context/         │
└────────────────────────────────────────────────────────────┘
```

---

## 3. Agent 设计

### 3.1 Lab-Orchestrator（主调度器）

| 属性 | 值 |
|------|---|
| **文件** | `agent/lab-orchestrator.md` |
| **职责** | 接收飞书消息，识别问题类型，路由到子Agent，整合回复 |
| **路由逻辑** | 关键词匹配 + LLM 意图识别 |
| **上下文级别** | Level 1 (隔离)，仅加载 routing map |

**路由规则**:

| 关键词/意图 | 路由目标 | 上下文级别 |
|------------|---------|-----------|
| 设备、GPU、服务器、仪器、机房 | Device-Agent | Level 2 |
| 项目、进度、负责人、里程碑、需求 | Project-Agent | Level 2 |
| 论文、文档、流程、规范、教程 | Knowledge-Agent | Level 2 |
| 混合意图 | 按优先级依次查询 | Level 2 |

### 3.2 Device-Agent

| 属性 | 值 |
|------|---|
| **文件** | `agent/subagents/device-agent.md` |
| **知识库** | `context/devices/` |
| **触发** | 设备/资产/硬件相关问题 |
| **输出** | 结构化设备信息（名称、位置、状态、负责人、维护记录） |

### 3.3 Project-Agent

| 属性 | 值 |
|------|---|
| **文件** | `agent/subagents/project-agent.md` |
| **知识库** | `context/projects/` |
| **触发** | 项目进度、人员分工、里程碑、文档相关问题 |
| **输出** | 项目概况 + 具体细节 + 引用来源 |

### 3.4 Knowledge-Agent

| 属性 | 值 |
|------|---|
| **文件** | `agent/subagents/knowledge-agent.md` |
| **知识库** | `context/knowledge/` + `context/guides/` |
| **触发** | 论文、技术调研、规范流程、教程相关问题 |
| **输出** | 知识总结 + 关键要点 + 引用来源 |

---

## 4. 知识库设计

### 4.1 目录结构

```
context/
├── navigation.md          # 知识库总索引（必读）
├── devices/               # 设备资产
│   ├── 设备总览.md         # 所有设备清单
│   └── {设备名}.md        # 单设备详情
├── projects/              # 项目管理
│   ├── 项目总览.md         # 所有项目状态
│   └── {项目名}.md        # 单项目详情
├── knowledge/             # 知识文档
│   ├── 论文笔记/
│   └── 技术调研/
└── guides/                # 流程规范
    ├── 新人入职指南.md
    └── 代码提交规范.md
```

### 4.2 文件模板规范

每个知识文件使用统一 frontmatter + 结构化内容：

```markdown
---
type: device | project | knowledge | guide
tags: [标签1, 标签2]
updated: 2026-05-07
author: 张三
---

# 标题

## 基本信息 / 项目概况
...

## 详细内容
...

## 相关链接 / 维护记录
...
```

---

## 5. 文档预处理管道

### 5.1 处理流程

```
raw-docs/*.docx  ──→ python-docx  ──→ context/**/*.md
raw-docs/*.pptx  ──→ python-pptx  ──→ context/**/*.md + images/
raw-docs/*.xlsx  ──→ openpyxl    ──→ context/**/*.md
raw-docs/*.pdf   ──→ PDF skill   ──→ context/**/*.md
raw-docs/*.md    ──→ 直接复制     ──→ context/**/*.md
```

### 5.2 使用方式

管理员日常操作：
1. 将新文件丢入 `raw-docs/`
2. 运行 `./scripts/convert.sh`
3. 检查转换结果（在 `context/` 下）

---

## 6. 飞书集成

### 6.1 方案

```
飞书开放平台 → 创建应用 → 事件订阅（机器人@提及）
                              ↓
                        Webhook URL
                              ↓
                    scripts/feishu-webhook.py
                              ↓
                       Lab-Orchestrator
                              ↓
                    飞书API → 回复消息（富文本）
```

### 6.2 所需飞书权限

- `im:message:send_as_bot` — 发送消息
- `im:message:read` — 读取消息
- 事件订阅：`im.message.receive_v1`

---

## 7. 自定义命令

| 命令 | Agent | 用途 |
|------|-------|------|
| `/查设备 <关键词>` | Device-Agent | 查询设备信息 |
| `/查项目 <关键词>` | Project-Agent | 查询项目信息 |
| `/查文档 <关键词>` | Knowledge-Agent | 查询知识文档 |
| `/更新知识库` | Orchestrator | 触发文档预处理管道 |

---

## 8. 设计决策记录 (ADR)

### ADR-001: 选择 Markdown 作为统一知识格式

**决策**: 所有知识文件统一为 Markdown（.md）格式。

**理由**:
- Markdown 是人类可读、版本控制友好的纯文本格式
- LLM 对 Markdown 理解效果最佳
- 支持 frontmatter 元数据，便于检索
- 多格式源文件通过预处理管道转为 Markdown

**替代方案**:
- 向量数据库（Chroma/Pinecone）：MVP 阶段过重，维护成本高
- 纯文本：缺少结构化，检索精度差

### ADR-002: 选择 .opencode Agent 体系而非独立后端

**决策**: 使用 .opencode 的 Agent 体系和 context/ 文件结构管理知识库。

**理由**:
- 当前环境已有 .opencode 支持
- 知识库即文件，无需数据库或后端服务
- Multi-Agent 路由天然适合多领域问答
- 扩展成本低，后续可平滑演进到全栈方案

---

## 9. 文件清单

| 文件 | 说明 |
|------|------|
| `agent/lab-orchestrator.md` | 主调度 Agent |
| `agent/subagents/device-agent.md` | 设备查询 Agent |
| `agent/subagents/project-agent.md` | 项目查询 Agent |
| `agent/subagents/knowledge-agent.md` | 知识查询 Agent |
| `context/navigation.md` | 知识库总索引 |
| `context/devices/设备总览.md` | 设备清单模板 |
| `context/projects/项目总览.md` | 项目总览模板 |
| `context/guides/新人入职指南.md` | 入职流程模板 |
| `context/guides/代码提交规范.md` | 代码规范模板 |
| `scripts/convert.sh` | 文档转换脚本 |
| `scripts/feishu-webhook.py` | 飞书 Webhook 处理器 |
| `workflows/answer-query.md` | 问答工作流 |
| `workflows/update-knowledge.md` | 知识更新工作流 |
| `commands/查设备.md` | /查设备 命令 |
| `commands/查项目.md` | /查项目 命令 |
| `commands/查文档.md` | /查文档 命令 |
| `commands/更新知识库.md` | /更新知识库 命令 |
| `ARCHITECTURE.md` | 本文档 |
| `QUICK-START.md` | 快速开始指南 |
| `TESTING.md` | 测试清单 |
