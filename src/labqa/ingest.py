"""
知识库入库模块
加载 .opencode/context/ 下的 Markdown 文件 → 分块 → FAISS 向量索引 + BM25 稀疏索引

用法:
  python -m labqa.ingest            # 构建/重建索引
  python -m labqa.ingest --check    # 检查索引状态
"""

import os
import sys
import pickle
import argparse
from pathlib import Path
from typing import List, Optional, Dict, Tuple

from langchain_core.documents import Document as LCDocument
from langchain_text_splitters import CharacterTextSplitter, RecursiveCharacterTextSplitter

from .config import (
    CONTEXT_DIR, FAISS_INDEX_DIR, BM25_INDEX_PATH,
    CHUNK_SIZE, CHUNK_OVERLAP, RETRIEVE_K, DEBUG,
)


def load_markdown_files(base_dir: Path) -> List[LCDocument]:
    """
    加载知识库目录下的所有 Markdown 文件
    解析 YAML frontmatter，跳过 navigation.md
    """
    documents = []

    if not base_dir.exists():
        print(f"⚠️ 知识库目录不存在: {base_dir}")
        return documents

    for md_file in base_dir.rglob("*.md"):
        # 跳过导航文件
        if md_file.name == "navigation.md":
            continue

        try:
            raw = md_file.read_text(encoding="utf-8")
        except Exception as e:
            print(f"⚠️ 读取失败: {md_file}: {e}")
            continue

        # 解析 frontmatter
        frontmatter: Dict[str, str] = {}
        content = raw
        if raw.startswith("---"):
            parts = raw.split("---", 2)
            if len(parts) >= 3:
                fm_text = parts[1].strip()
                for line in fm_text.split("\n"):
                    if ":" in line:
                        key, _, value = line.partition(":")
                        frontmatter[key.strip()] = value.strip()
                content = parts[2].strip()

        # 确定分类
        relative = str(md_file.relative_to(base_dir))
        category = relative.split("/")[0] if "/" in relative else "root"

        # 元数据
        metadata = {
            "source": relative,
            "filename": md_file.name,
            "category": category,
            "type": frontmatter.get("type", ""),
            "tags": frontmatter.get("tags", ""),
            "updated": frontmatter.get("updated", ""),
        }

        if content.strip():
            documents.append(LCDocument(page_content=content, metadata=metadata))

    if DEBUG:
        print(f"\n[Ingest] 加载了 {len(documents)} 个文档")
        for doc in documents:
            print(f"  - {doc.metadata['source']} ({doc.metadata['category']})")

    return documents


def split_documents(
    documents: List[LCDocument],
    chunk_size: int = CHUNK_SIZE,
    chunk_overlap: int = CHUNK_OVERLAP,
) -> List[LCDocument]:
    """
    文本分块：按段落分隔，保持语义连贯
    对中文内容，使用 RecursiveCharacterTextSplitter 效果更好
    """
    text_splitter = RecursiveCharacterTextSplitter(
        separators=["\n\n", "\n", "。", "！", "？", "；", " ", ""],
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        length_function=len,
        add_start_index=True,
    )
    chunks = text_splitter.split_documents(documents)

    if DEBUG:
        print(f"\n[Ingest] 分块完成: {len(documents)} 文档 → {len(chunks)} 块")
        if chunks:
            sample = chunks[min(10, len(chunks) - 1)]
            print(f"  示例块: {sample.page_content[:100]}...")

    return chunks


def build_faiss_index(
    chunks: List[LCDocument],
    embed_model,
    index_dir: Path = FAISS_INDEX_DIR,
    force_rebuild: bool = False,
):
    """
    构建 FAISS 向量索引（稠密检索）
    已存在索引则直接加载，force_rebuild=True 强制重建
    """
    from langchain_community.vectorstores import FAISS

    if not force_rebuild and index_dir.exists() and (index_dir / "index.faiss").exists():
        print(f"📦 检测到已有 FAISS 索引，加载中...")
        try:
            return FAISS.load_local(
                str(index_dir), embed_model,
                allow_dangerous_deserialization=True
            )
        except Exception as e:
            print(f"⚠️ FAISS 索引加载失败: {e}，将重建索引")

    print(f"🔍 构建 FAISS 向量索引 ({len(chunks)} 个文档块)...")
    index_dir.mkdir(parents=True, exist_ok=True)

    vectorstore = FAISS.from_documents(
        documents=chunks,
        embedding=embed_model,
    )
    vectorstore.save_local(str(index_dir))
    print(f"   FAISS 索引已保存: {index_dir}/index.faiss")
    return vectorstore


def build_bm25_index(
    chunks: List[LCDocument],
    index_path: Path = BM25_INDEX_PATH,
    force_rebuild: bool = False,
) -> Dict:
    """
    构建 BM25 倒排索引（稀疏检索）
    使用 jieba 分词增强中文支持（如可用），否则退化为字符级分词
    """
    from rank_bm25 import BM25Okapi

    if not force_rebuild and index_path.exists():
        print(f"📦 检测到已有 BM25 索引，加载中...")
        try:
            with open(index_path, "rb") as f:
                return pickle.load(f)
        except Exception as e:
            print(f"⚠️ BM25 索引加载失败: {e}，将重建索引")

    print(f"🔍 构建 BM25 索引 ({len(chunks)} 个文档块)...")

    # 中文分词
    try:
        import jieba
        def tokenize(text: str) -> List[str]:
            return list(jieba.cut(text.lower()))
        print("   使用 jieba 分词")
    except ImportError:
        def tokenize(text: str) -> List[str]:
            # 回退：字符 + 空格分词
            import re
            tokens = re.findall(r'[一-鿿]|[a-zA-Z]+|\d+', text.lower())
            return tokens
        print("   使用字符级分词（pip install jieba 以启用中文分词）")

    doc_texts = [chunk.page_content for chunk in chunks]
    tokenized_corpus = [tokenize(text) for text in doc_texts]
    bm25 = BM25Okapi(tokenized_corpus)

    bm25_data = {
        "bm25": bm25,
        "documents": chunks,
        "doc_texts": doc_texts,
        "tokenized_corpus": tokenized_corpus,
    }

    with open(index_path, "wb") as f:
        pickle.dump(bm25_data, f)
    print(f"   BM25 索引已保存: {index_path}")

    return bm25_data


def build_indexes(
    embed_model,
    force_rebuild: bool = False,
) -> Tuple:
    """一键构建/加载所有索引"""
    print("📚 加载知识库文档...")
    documents = load_markdown_files(CONTEXT_DIR)

    if not documents:
        print("⚠️ 知识库为空！请先添加文档到 .opencode/context/")
        return None, None, []

    chunks = split_documents(documents)
    print(f"   已加载 {len(documents)} 个文档，切分为 {len(chunks)} 个块")

    faiss_store = build_faiss_index(chunks, embed_model, force_rebuild=force_rebuild)
    bm25_data = build_bm25_index(chunks, force_rebuild=force_rebuild)

    print("✅ 所有索引就绪\n")
    return faiss_store, bm25_data, chunks


def check_indexes() -> Dict:
    """检查索引状态"""
    status = {
        "faiss_exists": (FAISS_INDEX_DIR / "index.faiss").exists(),
        "bm25_exists": BM25_INDEX_PATH.exists(),
        "context_exists": CONTEXT_DIR.exists(),
        "document_count": 0,
    }

    if status["context_exists"]:
        docs = load_markdown_files(CONTEXT_DIR)
        status["document_count"] = len(docs)

    return status


# ===== CLI =====
def main():
    parser = argparse.ArgumentParser(description="LabQA-RAG 知识库入库工具")
    parser.add_argument("--check", action="store_true", help="检查索引状态")
    parser.add_argument("--rebuild", action="store_true", help="强制重建所有索引")
    parser.add_argument("--stats", action="store_true", help="显示知识库统计")
    args = parser.parse_args()

    if args.check:
        status = check_indexes()
        print("📊 索引状态:")
        print(f"   FAISS 索引: {'✅ 存在' if status['faiss_exists'] else '❌ 未构建'}")
        print(f"   BM25 索引:  {'✅ 存在' if status['bm25_exists'] else '❌ 未构建'}")
        print(f"   知识库目录: {'✅ 存在' if status['context_exists'] else '❌ 不存在'}")
        print(f"   文档数量:   {status['document_count']}")
        return

    if args.stats:
        docs = load_markdown_files(CONTEXT_DIR)
        print(f"📚 知识库统计: {len(docs)} 个文档")
        by_cat: Dict[str, int] = {}
        for doc in docs:
            cat = doc.metadata.get("category", "unknown")
            by_cat[cat] = by_cat.get(cat, 0) + 1
        for cat, count in sorted(by_cat.items()):
            print(f"   {cat}/ : {count} 个文件")
        return

    # 构建索引
    from .generator import create_embeddings
    embed_model = create_embeddings()
    build_indexes(embed_model, force_rebuild=args.rebuild)


if __name__ == "__main__":
    main()
