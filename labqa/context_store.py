"""
上下文存储与检索 — 加载 context/ 目录下的知识文件，提供检索能力
"""

import re
from pathlib import Path
from typing import List, Dict, Optional

from .config import CONTEXT_DIR, DEBUG


class ContextFile:
    """单个知识文件"""

    def __init__(self, path: Path):
        self.path = path
        self.filename = path.name
        self.relative_path = str(path.relative_to(CONTEXT_DIR))
        self.category = self._detect_category()
        self.frontmatter: Dict[str, str] = {}
        self.content: str = ""
        self._load()

    def _detect_category(self) -> str:
        """从路径推断分类"""
        parts = self.relative_path.split("/")
        if len(parts) > 1:
            return parts[0]  # devices, projects, knowledge, guides
        return "root"

    def _load(self):
        """加载文件内容，解析 frontmatter"""
        try:
            raw = self.path.read_text(encoding="utf-8")
        except Exception as e:
            print(f"⚠️ 读取文件失败: {self.path}: {e}")
            self.content = ""
            return

        # 解析 YAML frontmatter (--- ... ---)
        if raw.startswith("---"):
            parts = raw.split("---", 2)
            if len(parts) >= 3:
                fm_text = parts[1].strip()
                # 简单解析 key: value
                for line in fm_text.split("\n"):
                    if ":" in line:
                        key, _, value = line.partition(":")
                        self.frontmatter[key.strip()] = value.strip()
                self.content = parts[2].strip()
            else:
                self.content = raw
        else:
            self.content = raw

    def get_summary(self, max_chars: int = 300) -> str:
        """获取内容摘要"""
        if len(self.content) <= max_chars:
            return self.content
        return self.content[:max_chars] + "..."

    def matches_keywords(self, keywords: List[str]) -> int:
        """
        关键词匹配打分
        返回匹配分数（越高越相关）
        """
        score = 0
        text = (self.filename + " " + self.content).lower()

        for kw in keywords:
            kw_lower = kw.lower()
            # 文件名匹配权重更高
            if kw_lower in self.filename.lower():
                score += 10
            # 内容匹配
            count = text.count(kw_lower)
            score += min(count * 2, 10)  # 最多10分
            # frontmatter tags 匹配
            tags = self.frontmatter.get("tags", "").lower()
            if kw_lower in tags:
                score += 5

        return score


class ContextStore:
    """知识库管理器"""

    def __init__(self):
        self.files: List[ContextFile] = []
        self._loaded = False

    def load_all(self):
        """加载所有知识文件"""
        if self._loaded:
            return

        if not CONTEXT_DIR.exists():
            print(f"⚠️ 知识库目录不存在: {CONTEXT_DIR}")
            return

        md_files = list(CONTEXT_DIR.rglob("*.md"))
        self.files = [ContextFile(f) for f in md_files]

        if DEBUG:
            print(f"\n[ContextStore] 加载了 {len(self.files)} 个知识文件:")
            for f in self.files:
                print(f"  - {f.relative_path} ({f.category})")

        self._loaded = True

    def reload(self):
        """重新加载知识库"""
        self._loaded = False
        self.files = []
        self.load_all()

    def search(
        self,
        keywords: List[str],
        category: Optional[str] = None,
        top_k: int = 5,
    ) -> List[ContextFile]:
        """
        搜索知识库

        Args:
            keywords: 搜索关键词列表
            category: 限定搜索分类 (devices/projects/knowledge/guides)，None表示全部
            top_k: 返回最相关的前K个文件

        Returns:
            按相关性排序的文件列表
        """
        self.load_all()

        # 过滤分类
        candidates = self.files
        if category and category != "root":
            candidates = [f for f in candidates if f.category == category]
            # 如果指定分类无结果，降级到全量搜索
            if not candidates:
                candidates = self.files

        # 跳过导航文件
        candidates = [f for f in candidates if f.filename != "navigation.md"]

        # 关键词打分
        scored = [(f, f.matches_keywords(keywords)) for f in candidates]
        scored.sort(key=lambda x: x[1], reverse=True)

        # 取 top_k 个有分数的
        results = [f for f, score in scored if score > 0][:top_k]

        if DEBUG:
            print(f"\n[ContextStore] 搜索关键词: {keywords}")
            print(f"[ContextStore] 分类过滤: {category or '全部'}")
            print(f"[ContextStore] 搜索结果 ({len(results)}/{len(scored)}):")
            for f, score in scored[:top_k]:
                print(f"  - {f.relative_path} (分数: {score})")

        return results

    def get_context_text(
        self,
        keywords: List[str],
        category: Optional[str] = None,
        top_k: int = 5,
        max_chars_per_file: int = 2000,
    ) -> str:
        """
        搜索并拼接为 LLM 可用的上下文字符串

        Args:
            keywords: 搜索关键词
            category: 限定分类
            top_k: 返回文件数
            max_chars_per_file: 每个文件最大字符数

        Returns:
            拼接后的上下文字符串
        """
        files = self.search(keywords, category, top_k)

        if not files:
            return "（知识库中未找到相关内容）"

        parts = []
        for f in files:
            content = f.content[:max_chars_per_file]
            parts.append(
                f"### 📄 {f.relative_path}\n"
                f"**标签**: {f.frontmatter.get('tags', '无')}\n"
                f"**更新**: {f.frontmatter.get('updated', '未知')}\n\n"
                f"{content}\n"
            )

        return "\n---\n\n".join(parts)

    def get_stats(self) -> Dict:
        """获取知识库统计信息"""
        self.load_all()
        stats = {"total": len(self.files), "by_category": {}}
        for f in self.files:
            cat = f.category
            stats["by_category"][cat] = stats["by_category"].get(cat, 0) + 1
        return stats


# 全局单例
_store: Optional[ContextStore] = None


def get_store() -> ContextStore:
    """获取知识库单例"""
    global _store
    if _store is None:
        _store = ContextStore()
    return _store
