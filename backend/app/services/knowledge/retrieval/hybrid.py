"""混合检索（hybrid mode）：vector + keyword 双路并发 + RRF 融合。

两路子检索各捞 top_k × HYBRID_LEG_FACTOR 条（融合层的视野），RRF 只吃
名次不吃分数——keyword 路 ts_rank 无 IDF、分数不可信，但名次仍有信息。
融合在应用层做、不写第三条 SQL：两路 SQL 各有讲究（vector 要事务内
SET LOCAL、keyword 要 Python 侧分词），硬拼一条会让三个文件互抄逻辑。
"""

import asyncio
import time
from dataclasses import dataclass
from uuid import UUID

from app.models import KnowledgeBase
from app.schemas.knowledge import RetrievalHit
from app.services.knowledge.retrieval.base import (
    RetrievalMode,
    RetrievalParams,
    RetrievalResult,
    Retriever,
)
from app.services.knowledge.retrieval.keyword import KeywordRetriever
from app.services.knowledge.retrieval.vector import VectorRetriever

# 每路候选深度 = top_k × 此倍数：融合的价值在「两榜都中等靠前」的段，
# 榜单不够长它们就上不了榜——融合救不了没见过的段；基准调参对象（×3/×5/×10）
HYBRID_LEG_FACTOR = 5

# 每路深度上限：vector 路内部还会 ×CANDIDATE_FACTOR(5) 开 ANN 候选池，
# 而 hnsw.ef_search 上限 1000——200 × 5 恰好顶格，防 top_k=50 时爆参
HYBRID_LEG_CAP = 200

# RRF 缓冲常数：压平单榜头部优势、让双榜共识胜出（Cormack 2009 经验值，
# ES / Azure / LlamaIndex 同款默认；对取值不敏感，不值得调参）
RRF_K = 60


@dataclass(slots=True)
class _FusedEntry:
    """融合过程的中间桶：累计 RRF 分 + 记住两路各自的命中（字段合并用）。"""
    rrf: float = 0.0
    vector_hit: RetrievalHit | None = None
    keyword_hit: RetrievalHit | None = None


class HybridRetriever(Retriever):
    """混合检索：并发跑 vector + keyword 两路，RRF 按名次融合。

    - similarity_threshold 下发给两条子路各自生效（各卡各的量纲：vector
      卡余弦、keyword 卡归一化 ts_rank），融合层不再卡分——RRF 融合分与
      0~1 阈值不同量纲，硬卡等于发明假语义；被一路筛掉的段仍可从另一路进场。
    - score = RRF 和 ÷ 理论最大值（双榜都第 1 = 1.0），得 0~1「共识分」，
      确定性公式、跨查询可比；原始 RRF 和最大仅 2/(RRF_K+1)≈0.033，
      直接渲染会像 bug。

    timings:
        embed_ms：query 向量化耗时（vector 路透传）
        vector_ms / keyword_ms：两路各自的检索 SQL 耗时（并发跑）
        fusion_ms：融合耗时（纯内存，通常 <1ms）
        search_ms：三者之和（兼容既有 Out 组装口径，语义=检索总开销）
    """

    mode = RetrievalMode.HYBRID

    _vector = VectorRetriever()
    _keyword = KeywordRetriever()

    async def retrieve(self, kb: KnowledgeBase, params: RetrievalParams) -> RetrievalResult:
        # 1. 两路并发进货（model_copy 刻意绕过 top_k le=50 的 API 校验——
        #    那是对外约束，内部放大是本 mode 的机制，深度另有 CAP 兜底）
        leg_top_k = min(params.top_k * HYBRID_LEG_FACTOR, HYBRID_LEG_CAP)
        leg_params = params.model_copy(update={"top_k": leg_top_k})
        vector_result, keyword_result = await asyncio.gather(
            self._vector.retrieve(kb, leg_params),
            self._keyword.retrieve(kb, leg_params),
        )
        # 2. RRF 融合 + top_k 交货
        t0 = time.perf_counter()
        hits = fuse_rrf(
            vector_result.hits, keyword_result.hits, params.top_k,
            vector_weight=params.vector_weight,
        )
        fusion_ms = round((time.perf_counter() - t0) * 1000, 2)

        embed_ms = vector_result.timings.get("embed_ms", 0.0)
        vector_ms = vector_result.timings.get("search_ms", 0.0)
        keyword_ms = keyword_result.timings.get("search_ms", 0.0)

        return RetrievalResult(
            hits=hits,
            timings={
                "embed_ms": embed_ms,
                "vector_ms": vector_ms,
                "keyword_ms": keyword_ms,
                "fusion_ms": fusion_ms,
                "search_ms": round(vector_ms + keyword_ms + fusion_ms, 1),
            },
        )


def fuse_rrf(
        vector_hits: list[RetrievalHit],
        keyword_hits: list[RetrievalHit],
        top_k: int,
        vector_weight: float = 0.5,
) -> list[RetrievalHit]:
    """RRF 按名次融合两路命中，返回共识分排序的前 top_k 段。

    纯函数（榜单进、榜单出），便于单测。名次从 1 起（论文口径），单路
    第 1 名贡献 1/(RRF_K+1)。入参榜单已按各自分数降序（SQL ORDER BY
    保证），名次 = 列表位置。同分并列时排序稳定：先 vector 榜、后 keyword 榜。
    字段合并向量优先：chunk_text 只有 vector 路有对应物。
    """
    entries: dict[UUID, _FusedEntry] = {}

    for rank, hit in enumerate(vector_hits, 1):
        entry = entries.setdefault(hit.paragraph_id, _FusedEntry())
        entry.rrf += vector_weight / (RRF_K + rank)
        entry.vector_hit = hit
    for rank, hit in enumerate(keyword_hits, 1):
        entry = entries.setdefault(hit.paragraph_id, _FusedEntry())
        entry.rrf += (1 - vector_weight) / (RRF_K + rank)
        entry.keyword_hit = hit

    max_rrf = 1 / (RRF_K + 1)  # 两路票权和为 1，双榜都第 1 的理论上限
    ranked = sorted(entries.values(), key=lambda e: e.rrf, reverse=True)[:top_k]

    hits: list[RetrievalHit] = []

    for entry in ranked:
        base = entry.vector_hit or entry.keyword_hit
        if entry.vector_hit and entry.keyword_hit:
            matched_by = "both"
        elif entry.vector_hit:
            matched_by = "vector"
        else:
            matched_by = "keyword"
        hits.append(base.model_copy(update={
            "score": round(entry.rrf / max_rrf, 4),
            "matched_by": matched_by,
        }))
    return hits
