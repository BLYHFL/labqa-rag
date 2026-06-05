"""
意图识别与路由引擎
分析用户输入，判断应路由到哪个 Agent

保留关键词匹配作为轻量级前置路由（快速、零成本），
底层检索已切换为 FAISS + BM25 混合检索
"""

from enum import Enum
from typing import List, Optional
from dataclasses import dataclass, field

from .config import DEBUG


class Intent(Enum):
    DEVICE = "device"
    PROJECT = "project"
    KNOWLEDGE = "knowledge"
    MIXED = "mixed"
    UNKNOWN = "unknown"


@dataclass
class RoutingDecision:
    """路由决策结果"""
    intent: Intent
    confidence: float
    target_agent: str
    matched_keywords: List[str] = field(default_factory=list)
    secondary_intents: List[Intent] = field(default_factory=list)


# 关键词库
DEVICE_KEYWORDS = [
    "设备", "服务器", "gpu", "cpu", "内存", "硬盘", "网络",
    "机柜", "仪器", "机器", "ip", "显卡", "算力",
    "a100", "h100", "v100", "4090", "h800", "a800",
    "空闲", "谁在用", "在哪", "坏了", "维修", "故障",
    "使用", "占用", "重启", "登录", "ssh",
    "nas", "存储", "数据盘", "硬盘",
    "测试车", "激光雷达", "采集套件", "传感器",
    "交换机", "工作站", "工位",
]

PROJECT_KEYWORDS = [
    "项目", "进度", "里程碑", "需求", "负责人", "排期",
    "ddl", "deadline", "交付", "上线", "测试", "外勤",
    "实验", "论文项目",
    "icml", "neurips", "cvpr", "iccv", "eccv", "iclr", "aaai",
    "截稿", "投稿", "会议",
    "谁负责", "谁在做", "在做什么",
    "llm", "rlhf", "dpo", "对齐", "自动驾驶", "感知",
    "融合", "小样本", "预研", "探索",
    "进展", "赶得上", "来得及",
]

KNOWLEDGE_KEYWORDS = [
    "论文", "文档", "调研", "规范", "流程", "教程", "指南",
    "怎么做", "怎么配置", "怎么申请", "怎么提交",
    "规范是什么", "要求是什么",
    "入职", "离职", "新人", "代码规范", "提交规范",
    "权限", "账号", "密码",
    "论文笔记", "论文讲了什么", "论文内容", "论文总结",
    "方法对比", "技术分析", "核心方法",
    "dpo", "rlhf", "transformer", "attention",
    "ppo", "kto", "sft",
    "区别", "对比", "哪个更好", "优缺点",
]

# 意图 → Agent 映射
AGENT_MAP = {
    Intent.DEVICE: "Device-Agent",
    Intent.PROJECT: "Project-Agent",
    Intent.KNOWLEDGE: "Knowledge-Agent",
}

# 意图 → 分类目录映射
INTENT_CATEGORY_MAP = {
    Intent.DEVICE: "devices",
    Intent.PROJECT: "projects",
    Intent.KNOWLEDGE: None,  # None = 搜索全部
}


def extract_keywords(text: str) -> List[str]:
    """从用户消息中提取关键词"""
    import re
    text_lower = text.lower()
    words = set()

    # 中文：按常见分隔切分
    for part in text.replace("，", " ").replace("？", " ").replace("。", " ").split():
        part = part.strip()
        if len(part) >= 2:
            words.add(part.lower())

    # 特殊实体：型号如 A100, H100
    model_pattern = re.findall(r'[a-zA-Z]\d+', text)
    words.update(m.lower() for m in model_pattern)

    return list(words)


def _score_intent(text: str, keywords: List[str], intent_keywords: List[str]) -> int:
    """计算某意图的匹配分数"""
    score = 0
    text_lower = text.lower()

    for kw in intent_keywords:
        kw_lower = kw.lower()
        if kw_lower in text_lower:
            if len(kw) <= 3:
                score += 1
            else:
                score += 2
        if kw_lower in keywords:
            score += 1

    return score


def recognize_intent(text: str) -> RoutingDecision:
    """
    识别用户意图并做出路由决策

    两层策略:
    1. 关键词匹配（快速，零成本）
    2. 未来可扩展为 LLM 路由（更准确但更慢）
    """
    text_lower = text.lower()
    keywords = extract_keywords(text)

    scores = {
        Intent.DEVICE: _score_intent(text_lower, keywords, DEVICE_KEYWORDS),
        Intent.PROJECT: _score_intent(text_lower, keywords, PROJECT_KEYWORDS),
        Intent.KNOWLEDGE: _score_intent(text_lower, keywords, KNOWLEDGE_KEYWORDS),
    }

    max_score = max(scores.values())
    if max_score == 0:
        return RoutingDecision(
            intent=Intent.UNKNOWN,
            confidence=0.0,
            target_agent="none",
        )

    primary = next(k for k, v in scores.items() if v == max_score)

    # 混合意图
    secondary = [
        k for k, v in scores.items()
        if k != primary and v > 0 and v >= max_score * 0.5
    ]

    # 匹配到的关键词
    all_kw_lists = {
        Intent.DEVICE: DEVICE_KEYWORDS,
        Intent.PROJECT: PROJECT_KEYWORDS,
        Intent.KNOWLEDGE: KNOWLEDGE_KEYWORDS,
    }
    matched_kw = [kw for kw in all_kw_lists[primary] if kw in text_lower]

    confidence = min(max_score / 5.0, 1.0)

    if DEBUG:
        print(f"\n[Router] 消息: {text[:100]}...")
        print(f"[Router] 分数: device={scores[Intent.DEVICE]}, "
              f"project={scores[Intent.PROJECT]}, knowledge={scores[Intent.KNOWLEDGE]}")
        print(f"[Router] 主意图: {primary.value} (置信度: {confidence:.2f})")
        if secondary:
            print(f"[Router] 次要意图: {[s.value for s in secondary]}")

    return RoutingDecision(
        intent=Intent.MIXED if secondary else primary,
        confidence=confidence,
        target_agent=AGENT_MAP[primary],
        matched_keywords=matched_kw,
        secondary_intents=secondary,
    )


def get_intent_category(intent: Intent) -> Optional[str]:
    """获取意图对应的知识库分类目录"""
    return INTENT_CATEGORY_MAP.get(intent)
