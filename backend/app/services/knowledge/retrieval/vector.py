"""向量检索（v1 默认 mode）。

query 向量化 → HNSW 按距离捞候选池（内层 LIMIT，索引唯一出力点）
→ 按段去重（DISTINCT ON）→ 阈值过滤 → top_k。
Tortoise 不支持 pgvector 算子，核心查询走原生 SQL（sql/vector_search.sql）。
"""
import time

from tortoise.transactions import in_transaction
from app.models import KnowledgeBase
from app.schemas.knowledge import RetrievalHit
from app.services.knowledge.retrieval.base import (
    RetrievalMode,
    RetrievalParams,
    RetrievalResult,
    Retriever,
)
from app.services.knowledge.retrieval.sql import load_sql
from app.services.model import ModelClient

# 内层 ANN 候选池 = top_k × 此倍数：同段多块挤占名额 + 阈值过滤都要备胎；
# 本质是「召回换延迟」的旋钮，调参基准实验的对象
CANDIDATE_FACTOR = 5


def _to_vector_literal(vec: list[float]) -> str:
    """list[float] → pgvector 文本字面量 '[1,2,3]'（作为 $ 参数传入、查询里再 cast）。"""
    return "[" + ",".join(str(float(x)) for x in vec) + "]"


class VectorRetriever(Retriever):
    """纯向量检索。

    timings:
        embed_ms：query 向量化耗时（调 embedding 模型，网络请求，通常占大头）
        search_ms：pgvector 检索 SQL 耗时（本地 DB，通常很快）
    """

    mode = RetrievalMode.VECTOR

    async def retrieve(self, kb: KnowledgeBase, params: RetrievalParams) -> RetrievalResult:
        t0 = time.perf_counter()

        # 1. query 向量化（一条文本 → 一条向量）
        #    注：BGE query 指令前缀已实测（2026-07-17，Multi-CPR 1 万段 ×1000 题）：
        #    v1.5 仅 +0.2pt recall@10 / +1pt MRR@10，决策不加（省掉按模型维护指令表，
        #    与 Dify/RAGFlow 取舍一致）。档案见 benchmarks/results/2026-07-17_00*.json。
        vectors = await ModelClient.create_embedding(kb.embedding_model, [params.query.strip()])
        query_literal = _to_vector_literal(vectors[0])
        t1 = time.perf_counter()

        # 2. 原生 SQL 检索（sql/vector_search.sql）：
        #    HNSW 捞候选（内层 LIMIT 候选池）→ 按段去重 → 阈值 → top_k。
        #    {dim} 是类型修饰符（不能参数化），format 拼入；其余值全走 $ 参数（防注入）。
        #    SQL 里 ORDER BY 的 cast 表达式须与按库建的 HNSW 部分索引定义一致才命中索引。
        dim = kb.embedding_dim
        pool = params.top_k * CANDIDATE_FACTOR

        sql = load_sql("vector_search").format(dim=dim)

        # SET LOCAL 只在事务内生效；ef_search 是 HNSW 的候选名单深度：
        # 低于候选池会截胡池子，低于默认 40 会让搜索变浅——取两者较大值
        async with in_transaction() as conn:
            # 规划器对 1024 维距离计算的成本严重低估，小表上会误选顺扫
            # （实测 10k 行：顺扫 176ms vs HNSW 3ms）；把顺扫标成天价强制走索引，
            # 无索引的库 PG 仍会顺扫兜底不报错。SET LOCAL 出事务自动还原。
            await conn.execute_query("SET LOCAL enable_seqscan = off")
            await conn.execute_query(f"SET LOCAL hnsw.ef_search = {max(int(pool), 40)}")
            rows = await conn.execute_query_dict(
                sql,
                [query_literal, kb.id, params.similarity_threshold, params.top_k, pool],
            )
        t2 = time.perf_counter()

        # 3. 组装：score = 1 - 余弦距离
        hits = [
            RetrievalHit(
                paragraph_id=row["paragraph_id"],
                document_id=row["document_id"],
                doc_name=row["doc_name"],
                title=row["title"],
                content=row["content"],
                chunk_text=row["chunk_text"],
                score=1 - row["distance"],
            )
            for row in rows
        ]
        return RetrievalResult(
            hits=hits,
            timings={
                "embed_ms": round((t1 - t0) * 1000, 1),
                "search_ms": round((t2 - t1) * 1000, 1),
            },
        )