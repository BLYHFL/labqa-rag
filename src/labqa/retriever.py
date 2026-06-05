"""
混合检索模块 — FAISS 向量检索 + BM25 稀疏检索 + RRF 融合

参考: helloworldtang/langchain-rag-tutorial
"""

import pickle
from typing import List, Dict, Optional, Tuple

from langchain_core.documents import Document as LCDocument

from .config import (
    FAISS_INDEX_DIR, BM25_INDEX_PATH, RETRIEVE_K, FUSION_K, RRF_K, DEBUG,
)


# ===== FAISS 稠密检索 =====

def dense_search(
    vectorstore,
    query: str,
    k: int = RETRIEVE_K,
    category_filter: Optional[str] = None,
) -> List[Dict]:
    """
    FAISS 向量相似度搜索（稠密检索）
    返回: [{"doc": LCDocument, "score": float}, ...]
    """
    try:
        if category_filter:
            # 带分类过滤的检索：先多取一些结果，再过滤
            docs_with_scores = vectorstore.similarity_search_with_relevance_scores(
                query, k=k * 3
            )
        else:
            docs_with_scores = vectorstore.similarity_search_with_relevance_scores(
                query, k=k
            )

        results = []
        for doc, score in docs_with_scores:
            if category_filter and doc.metadata.get("category") != category_filter:
                continue
            results.append({"doc": doc, "score": float(score)})
            if len(results) >= k:
                break

        return results
    except Exception as e:
        if DEBUG:
            print(f"⚠️ FAISS 检索失败: {e}")
        return []


# ===== BM25 稀疏检索 =====

def sparse_search(
    bm25_data: Dict,
    query: str,
    k: int = RETRIEVE_K,
    category_filter: Optional[str] = None,
) -> List[Dict]:
    """
    BM25 关键词检索（稀疏检索）
    支持中文分词（jieba）和分类过滤
    """
    if bm25_data is None:
        return []

    bm25 = bm25_data["bm25"]
    documents = bm25_data["documents"]

    # 中文分词
    try:
        import jieba
        tokenized_query = list(jieba.cut(query.lower()))
    except ImportError:
        import re
        tokenized_query = re.findall(r'[一-鿿]|[a-zA-Z]+|\d+', query.lower())

    if not tokenized_query:
        return []

    scores = bm25.get_scores(tokenized_query)

    # 按分数排序
    indexed = list(enumerate(scores))
    indexed.sort(key=lambda x: x[1], reverse=True)

    results = []
    for idx, score in indexed[:k * 3]:  # 多取一些以便分类过滤
        if score <= 0:
            continue
        doc = documents[idx]
        if category_filter and doc.metadata.get("category") != category_filter:
            continue
        results.append({"doc": doc, "score": float(score)})
        if len(results) >= k:
            break

    return results


# ===== RRF 融合算法 =====

def reciprocal_rank_fusion(
    results_list: List[List[Dict]],
    k: int = RRF_K,
) -> List[Dict]:
    """
    RRF（倒数排名融合）算法

    核心思想: score = 1 / (k + rank)
    - 排名越靠前，贡献越大
    - 不同检索器中同一文档的分数累加
    - 两路检索结果综合排名

    Args:
        results_list: 多路检索结果，每路是 [{"doc": LCDocument, "score": float}, ...]
        k: RRF 参数，默认 60（经验值），越大两路越均衡

    Returns:
        融合后的结果列表，按 rrf_score 降序排列
    """
    doc_scores: Dict[str, Dict] = {}

    for retriever_results in results_list:
        for rank, item in enumerate(retriever_results, start=1):
            # 用 page_content 作为文档唯一标识
            doc_key = item["doc"].page_content
            if doc_key not in doc_scores:
                doc_scores[doc_key] = {"doc": item["doc"], "rrf_score": 0.0}
            # 累加 RRF 分数
            doc_scores[doc_key]["rrf_score"] += 1.0 / (k + rank)

    # 按综合分数降序排列
    fused = sorted(
        doc_scores.values(),
        key=lambda x: x["rrf_score"],
        reverse=True,
    )
    return fused


# ===== 混合检索 =====

def load_indexes(embed_model):
    """加载已有索引"""
    from langchain_community.vectorstores import FAISS

    faiss_store = None
    bm25_data = None

    # 加载 FAISS
    if (FAISS_INDEX_DIR / "index.faiss").exists():
        try:
            faiss_store = FAISS.load_local(
                str(FAISS_INDEX_DIR), embed_model,
                allow_dangerous_deserialization=True
            )
        except Exception as e:
            print(f"⚠️ FAISS 索引加载失败: {e}")

    # 加载 BM25
    if BM25_INDEX_PATH.exists():
        try:
            with open(BM25_INDEX_PATH, "rb") as f:
                bm25_data = pickle.load(f)
        except Exception as e:
            print(f"⚠️ BM25 索引加载失败: {e}")

    return faiss_store, bm25_data


def hybrid_search(
    vectorstore,
    bm25_data: Dict,
    query: str,
    top_k: int = FUSION_K,
    category_filter: Optional[str] = None,
    verbose: bool = False,
) -> List[LCDocument]:
    """
    混合检索完整流程:

    1. FAISS 向量检索 → Top-K（稠密，语义匹配）
    2. BM25 稀疏检索 → Top-K（稀疏，关键词匹配）
    3. RRF 融合 → 最终 Top-K 排名

    Args:
        vectorstore: FAISS 向量存储
        bm25_data: BM25 索引数据
        query: 用户查询
        top_k: 最终返回的文档数量
        category_filter: 可选的知识库分类过滤
        verbose: 是否打印检索过程

    Returns:
        融合后的文档列表（按 RRF 分数降序）
    """
    if verbose:
        print(f"   🔎 混合检索: query =「{query[:80]}...」" if len(query) > 80 else f"   🔎 混合检索: query =「{query}」")

    # Step 1: 两路并行检索
    dense_results = dense_search(vectorstore, query, k=RETRIEVE_K, category_filter=category_filter)
    sparse_results = sparse_search(bm25_data, query, k=RETRIEVE_K, category_filter=category_filter)

    if verbose:
        print(f"   📊 FAISS 命中: {len(dense_results)} 条 | BM25 命中: {len(sparse_results)} 条")

    # Step 2: BM25 无结果时降级为纯向量检索
    if not sparse_results:
        if verbose:
            print("   ⚠️ BM25 无结果，降级为纯向量检索")
        docs = [item["doc"] for item in dense_results[:top_k]]
        return docs

    # Step 3: RRF 融合
    fused = reciprocal_rank_fusion([dense_results, sparse_results], k=RRF_K)

    if verbose:
        print("   🏆 RRF 融合排名（Top-5）:")
        for i, item in enumerate(fused[:min(5, len(fused))], 1):
            preview = item["doc"].page_content[:60].replace("\n", " ")
            source = item["doc"].metadata.get("source", "?")
            print(f"      [{i}] RRF={item['rrf_score']:.3f} | {source} | {preview}...")

    # Step 4: 返回 Top-K
    return [item["doc"] for item in fused[:top_k]]


def search_by_category(
    vectorstore,
    bm25_data: Dict,
    query: str,
    category: str,
    top_k: int = FUSION_K,
) -> List[LCDocument]:
    """
    在指定分类下检索（用于 Agent 路由）
    """
    return hybrid_search(
        vectorstore, bm25_data, query,
        top_k=top_k, category_filter=category,
        verbose=DEBUG,
    )
