"""
意图识别与路由引擎
分析用户输入的关键词，判断应路由到哪个 Agent
"""

from enum import Enum
from typing import List, Tuple
from dataclasses import dataclass

from .config import DEBUG


class Intent(Enum):
    """意图分类"""
    DEVICE = "device"
    PROJECT = "project"
    KNOWLEDGE = "knowledge"
    MIXED = "mixed"
    UNKNOWN = "unknown"


@dataclass
class RoutingDecision:
    """路由决策结果"""
    intent: Intent
    confidence: float  # 0.0 - 1.0
    target_agent: str
    matched_keywords: List[str]
    secondary_intents: List[Intent]  # 混合意图时的次要意图


# 关键词库（从 Agent 定义中提取）
DEVICE_KEYWORDS = [
    # 设备
    "设备", "服务器", "gpu", "cpu", "内存", "硬盘", "网络",
    "机柜", "仪器", "机器", "ip", "显卡", "算力",
    # GPU型号
    "a100", "h100", "v100", "4090", "h800", "a800",
    # 状态
    "空闲", "谁在用", "在哪", "坏了", "维修", "故障",
    "使用", "占用", "重启", "登录", "ssh",
    # 存储
    "nas", "存储", "数据盘", "硬盘",
    # 外勤
    "测试车", "激光雷达", "采集套件", "传感器",
    "交换机", "工作站", "工位",
]

PROJECT_KEYWORDS = [
    # 项目
    "项目", "进度", "里程碑", "需求", "负责人", "排期",
    "ddl", "deadline", "交付", "上线", "测试", "外勤",
    "实验", "论文项目",
    # 会议/期刊
    "icml", "neurips", "cvpr", "iccv", "eccv", "iclr", "aaai",
    "截稿", "投稿", "会议",
    # 人员
    "谁负责", "谁在做", "在做什么",
    # 项目名/类型
    "llm", "rlhf", "dpo", "对齐", "自动驾驶", "感知",
    "融合", "小样本", "预研", "探索",
    # 状态
    "进展", "赶得上", "来得及",
]

KNOWLEDGE_KEYWORDS = [
    # 文档
    "论文", "文档", "调研", "规范", "流程", "教程", "指南",
    "怎么做", "怎么配置", "怎么申请", "怎么提交",
    "规范是什么", "要求是什么",
    # 流程
    "入职", "离职", "新人", "代码规范", "提交规范",
    "权限", "账号", "密码",
    # 论文相关
    "论文笔记", "论文讲了什么", "论文内容", "论文总结",
    "方法对比", "技术分析", "核心方法",
    # 论文名
    "dpo", "rlhf", "transformer", "attention",
    "ppo", "kto", "sft",
    # 比较
    "区别", "对比", "哪个更好", "优缺点",
]


def extract_keywords(text: str) -> List[str]:
    """从用户消息中提取关键词"""
    text_lower = text.lower()

    # 中文: 按常见分隔切分
    # 英文: 按空格和标点切分
    words = set()
    for part in text.replace("，", " ").replace("？", " ").replace("。", " ").split():
        part = part.strip()
        if len(part) >= 2:
            words.add(part.lower())

    # 特殊实体: 型号如 A100, H100
    import re
    model_pattern = re.findall(r'[a-zA-Z]\d+', text)
    words.update(m.lower() for m in model_pattern)

    return list(words)


def recognize_intent(text: str) -> RoutingDecision:
    """
    识别用户意图并做出路由决策

    Args:
        text: 用户消息文本

    Returns:
        RoutingDecision 路由决策
    """
    text_lower = text.lower()
    keywords = extract_keywords(text)

    # 计算各意图匹配分数
    scores = {
        Intent.DEVICE: _score_intent(text_lower, keywords, DEVICE_KEYWORDS),
        Intent.PROJECT: _score_intent(text_lower, keywords, PROJECT_KEYWORDS),
        Intent.KNOWLEDGE: _score_intent(text_lower, keywords, KNOWLEDGE_KEYWORDS),
    }

    # 找到主意图
    max_score = max(scores.values())
    if max_score == 0:
        return RoutingDecision(
            intent=Intent.UNKNOWN,
            confidence=0.0,
            target_agent="none",
            matched_keywords=[],
            secondary_intents=[],
        )

    primary = [k for k, v in scores.items() if v == max_score][0]

    # 检查是否有混合意图（次要意图分数 > 0 且 > 主意图的50%）
    secondary = [
        k for k, v in scores.items()
        if k != primary and v > 0 and v >= max_score * 0.5
    ]

    # 确定目标Agent
    agent_map = {
        Intent.DEVICE: "Device-Agent",
        Intent.PROJECT: "Project-Agent",
        Intent.KNOWLEDGE: "Knowledge-Agent",
    }

    # 匹配到的关键词
    all_kw_lists = {
        Intent.DEVICE: DEVICE_KEYWORDS,
        Intent.PROJECT: PROJECT_KEYWORDS,
        Intent.KNOWLEDGE: KNOWLEDGE_KEYWORDS,
    }
    matched_kw = [kw for kw in all_kw_lists[primary] if kw in text_lower]

    # 计算置信度
    confidence = min(max_score / 5.0, 1.0)

    if DEBUG:
        print(f"\n[Router] 消息: {text[:100]}...")
        print(f"[Router] 分词: {keywords}")
        print(f"[Router] 分数: device={scores[Intent.DEVICE]}, project={scores[Intent.PROJECT]}, knowledge={scores[Intent.KNOWLEDGE]}")
        print(f"[Router] 主意图: {primary.value} (置信度: {confidence:.2f})")
        print(f"[Router] 匹配词: {matched_kw}")
        if secondary:
            print(f"[Router] 次要意图: {[s.value for s in secondary]}")

    return RoutingDecision(
        intent=Intent.MIXED if secondary else primary,
        confidence=confidence,
        target_agent=agent_map[primary],
        matched_keywords=matched_kw,
        secondary_intents=secondary,
    )


def _score_intent(text: str, keywords: List[str], intent_keywords: List[str]) -> int:
    """
    计算某意图的匹配分数

    规则:
    - 短关键词(<=3字符)在文本中匹配: +1
    - 长关键词(>3字符)在文本中匹配: +2
    - 关键词在分词结果中精确匹配: +3
    """
    score = 0
    text_lower = text.lower()

    for kw in intent_keywords:
        kw_lower = kw.lower()
        if kw_lower in text_lower:
            if len(kw) <= 3:
                score += 1
            else:
                score += 2
        # 精确词匹配加分
        if kw_lower in keywords:
            score += 1

    return score
