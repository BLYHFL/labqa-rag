# LabQA 快速开始指南

## 第1步：了解系统架构

阅读 [ARCHITECTURE.md](docs/ARCHITECTURE.md) 了解系统整体设计。

## 第2步：充实知识库

知识库是系统的核心。启动时已包含以下空模板：

```
context/
├── navigation.md              ← 知识库总索引
├── devices/                   ← 设备信息
│   └── 设备总览.md             ← 填写你的设备清单
├── projects/                  ← 项目信息
│   └── 项目总览.md             ← 填写你的项目信息
├── knowledge/                 ← 知识文档
│   └── 论文笔记/               ← 放入论文笔记
└── guides/                    ← 流程规范
    ├── 新人入职指南.md         ← 按实际情况修改
    └── 代码提交规范.md         ← 按实际情况修改
```

### 如何填充知识库？

**方式一：直接编辑 Markdown**
```bash
# 用任意编辑器打开，直接改内容
code .opencode/context/devices/设备总览.md
```

**方式二：通过原始文档转换**
```bash
# 1. 将 Word/PPT/Excel/PDF 丢入 raw-docs/
cp 你的文档.docx raw-docs/

# 2. 运行转换脚本
bash scripts/convert.sh

# 3. 检查转换结果
ls .opencode/context/devices/
ls .opencode/context/projects/
```

## 第3步：本地测试问答

### 在终端对话中测试

直接在对话中向 Lab-Orchestrator 提问：

```
/查设备 GPU服务器
/查项目 论文项目
/查文档 入职流程
```

### 预期行为

| 命令 | 预期响应 |
|------|---------|
| `/查设备 GPU` | 返回设备总览中的GPU设备信息 |
| `/查项目 论文` | 返回学术论文项目的状态 |
| `/查文档 入职` | 返回新人入职指南内容 |
| `/查设备 不存在的设备` | 返回"未找到"提示 |
| 模糊问题 | 返回引导提示，说明支持的问题类型 |

## 第4步：接入飞书（可选）

### 4.1 安装依赖
```bash
pip install flask requests python-docx python-pptx openpyxl
```

### 4.2 创建飞书应用
1. 登录 [飞书开放平台](https://open.feishu.cn/)
2. 创建企业自建应用
3. 获取 App ID 和 App Secret
4. 配置机器人，开启以下权限：
   - `im:message:send_as_bot`
   - `im:message:read`

### 4.3 配置环境变量
```bash
export FEISHU_APP_ID="your-app-id"
export FEISHU_APP_SECRET="your-app-secret"
export FEISHU_VERIFICATION_TOKEN="your-verification-token"
```

### 4.4 启动服务
```bash
python3 scripts/feishu-webhook.py
```

### 4.5 配置 Webhook URL
在飞书开放平台配置事件订阅 URL：
```
http://<你的服务器IP>:8080/feishu/webhook
```

## 第5步：日常使用

### 管理员
1. 有新文档 → 丢入 `raw-docs/` → 运行 `scripts/convert.sh`
2. 定期更新设备总览、项目总览
3. 每周检查知识库完整性

### 实验室成员
1. 在飞书群 @机器人 提问
2. 或在终端使用 /查设备、/查项目、/查文档 命令

---

**下一步**: 阅读 [TESTING.md](docs/TESTING.md) 进行完整的功能验证。
