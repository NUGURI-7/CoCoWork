"""向量检索（v1 默认 mode）。

query 向量化 → pgvector 余弦距离排序 → 按段去重（DISTINCT ON）
→ 阈值过滤 → top_k。Tortoise 不支持 pgvector 算子，核心查询走原生 SQL。
"""
import time

from tortoise import connections

from app.models import KnowledgeBase
from app.schemas.knowledge import RetrievalHit
from app.services.knowledge.retrieval.base import (
    RetrievalMode,
    RetrievalParams,
    RetrievalResult,
    Retriever,
)
from app.services.model import ModelClient


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
        #    注：BGE/E5 等模型需 query 前缀（query: ...）才最优，v1 暂未加（known gap）。
        vectors = await ModelClient.create_embedding(kb.embedding_model, [params.query.strip()])
        query_literal = _to_vector_literal(vectors[0])
        t1 = time.perf_counter()

        # 2. 原生 SQL 检索：
        #    - 内层 DISTINCT ON (paragraph_id) 按段去重，每段取最近子块
        #    - 外层按距离重排、阈值过滤、取 top_k
        #    - {dim} 是类型修饰符（不能参数化），用本库锁定维度 f-string 拼入；
        #      其余 query 向量 / kb_id / 阈值 / top_k 全走 $ 参数（防注入）。
        #      cast 写法须与将来按库建的 HNSW 部分索引表达式一致才命中索引。
        dim = kb.embedding_dim
        sql = f"""
            SELECT sub.paragraph_id, sub.document_id, sub.doc_name,
                sub.content, sub.chunk_text, sub.distance
            FROM (
                SELECT DISTINCT ON (e.paragraph_id)
                e.paragraph_id, e.document_id, e.text AS chunk_text,
                e.embedding::vector({dim}) <=> $1::vector({dim}) AS distance,
                p.content, d.name AS doc_name
                FROM embeddings e
                JOIN paragraphs p ON p.id = e.paragraph_id
                JOIN documents d ON d.id = e.document_id
                WHERE e.knowledge_base_id = $2 AND e.source_type = 'content'
                ORDER BY e.paragraph_id, distance
            ) sub
            WHERE (1 - sub.distance) >= $3
            ORDER BY sub.distance
            LIMIT $4
        """

        conn = connections.get("default")
        rows = await conn.execute_query_dict(
            sql, [query_literal, kb.id, params.similarity_threshold, params.top_k],
        )
        t2 = time.perf_counter()

        # 3. 组装：score = 1 - 余弦距离
        hits = [
            RetrievalHit(
                paragraph_id=row["paragraph_id"],
                document_id=row["document_id"],
                doc_name=row["doc_name"],
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