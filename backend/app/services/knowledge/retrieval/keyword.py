"""全文检索（keyword mode）。

query 走 TF-IDF 关键词提取（tokenize_query，废词出局）→ 拼 OR tsquery
→ GIN 匹配 + ts_rank_cd 打分（sql/keyword_search.sql）。
不调 embedding 模型，零 API 成本。
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
from app.services.knowledge.retrieval.sql import load_sql
from app.services.knowledge.tokenization import tokenize_query

def _to_tsquery_literal(tokens: list[str]) -> str:
    """词序列 → OR 查询串："'词1' | '词2'"（引号/反斜杠双写，转义规则同 TSVectorField）。"""
    quoted = ["'" + t.replace("\\", "\\\\").replace("'", "''") + "'" for t in tokens]
    return " | ".join(quoted)


class KeywordRetriever(Retriever):
    """全文检索。

    timings:
        search_ms：检索 SQL 耗时（没有 embed 阶段——不花模型钱是本 mode 的卖点之一）
    """

    mode = RetrievalMode.KEYWORD

    async def retrieve(self, kb: KnowledgeBase, params: RetrievalParams) -> RetrievalResult:
        # 1. query 关键词提取——TF-IDF 只留前 K 个高信息量词（归一化口径与索引侧一致）
        tokens = tokenize_query(params.query)
        if not tokens:
            # query 全是标点/空白，切完没词：to_tsquery 会对空串报错，直接空手而归
            return RetrievalResult(hits=[], timings={"search_ms": 0.0})
        # 2. 原生 SQL（sql/keyword_search.sql）：GIN 匹配 → ts_rank_cd → 阈值 → top_k
        t0 = time.perf_counter()
        rows = await connections.get("default").execute_query_dict(
            load_sql("keyword_search"),
            [kb.id, _to_tsquery_literal(tokens), params.similarity_threshold, params.top_k],
        )
        t1 = time.perf_counter()

        # 3. 组装：命中的就是整段，chunk_text 无对应物、给空串
        hits = [
            RetrievalHit(
                paragraph_id=row["paragraph_id"],
                document_id=row["document_id"],
                doc_name=row["doc_name"],
                title=row["title"],
                content=row["content"],
                chunk_text="",
                score=row["score"],
            )
            for row in rows
        ]
        return RetrievalResult(
            hits=hits,
            timings={"search_ms": round((t1 - t0) * 1000, 1)},
        )










