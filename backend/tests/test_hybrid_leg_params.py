"""HybridRetriever 分腿参数分发 —— 桩掉两条腿，零 DB 零 API。

守的规矩：`similarity_threshold` 只绑 vector 腿，keyword 腿恒为 0。
ts_rank 未校准（无 IDF、量级远低于余弦），同一个阈值对两腿严厉度不同——
阈值一调高 keyword 腿先全军覆没，hybrid 会**静默**退化成纯向量，界面上
没有任何提示。顺带锁住「除阈值外两腿参数逐字一致」，防将来加字段漏配一边。
"""

from uuid import uuid4

from app.services.knowledge.retrieval.base import (
    RetrievalMode,
    RetrievalParams,
    RetrievalResult,
)
from app.services.knowledge.retrieval.hybrid import (
    HYBRID_LEG_CAP,
    HYBRID_LEG_FACTOR,
    HybridRetriever,
)


class _SpyLeg:
    """记下收到的 params 就交空榜——本测只关心入参怎么分发，不关心检索结果。"""

    def __init__(self):
        self.params: RetrievalParams | None = None

    async def retrieve(self, kb, params: RetrievalParams) -> RetrievalResult:
        self.params = params
        return RetrievalResult(hits=[], timings={"search_ms": 0.0})


async def _run(**overrides) -> tuple[_SpyLeg, _SpyLeg]:
    """跑一次 hybrid，返回两条腿各自收到的参数（kb 传 None：腿被桩掉、碰不到它）。"""
    retriever = HybridRetriever()
    vector_spy, keyword_spy = _SpyLeg(), _SpyLeg()
    # 实例属性遮蔽类属性，不污染其他用例
    retriever._vector, retriever._keyword = vector_spy, keyword_spy

    params = RetrievalParams(**{
        "query": "报销要多久", "top_k": 5, "similarity_threshold": 0.6,
        "mode": RetrievalMode.HYBRID, **overrides,
    })
    await retriever.retrieve(None, params)
    return vector_spy, keyword_spy


async def test_阈值只绑向量腿():
    """阈值 0.6：向量腿原样收到，关键词腿被置 0——不可信的分不许设卡。"""
    vector_spy, keyword_spy = await _run()

    assert vector_spy.params.similarity_threshold == 0.6
    assert keyword_spy.params.similarity_threshold == 0.0


async def test_阈值为零时两腿一致():
    """开精排时调度层已把阈值置 0，本层再置一次是幂等的，行为零变化。"""
    vector_spy, keyword_spy = await _run(similarity_threshold=0.0)

    assert vector_spy.params.similarity_threshold == 0.0
    assert keyword_spy.params.similarity_threshold == 0.0


async def test_除阈值外两腿参数逐字一致():
    """腿深、权重、query 都不许飘——两腿看的必须是同一道题、同样深。"""
    vector_spy, keyword_spy = await _run(vector_weight=0.7)

    v, k = vector_spy.params, keyword_spy.params
    assert v.model_dump(exclude={"similarity_threshold"}) == k.model_dump(
        exclude={"similarity_threshold"}
    )
    assert v.query == "报销要多久"
    assert v.vector_weight == 0.7


async def test_腿深按倍数放大且封顶():
    """腿深 = top_k × FACTOR，撞 CAP 封顶（top_k 放大绕过 API 的 le=50 校验）。"""
    vector_spy, _ = await _run(top_k=5)
    assert vector_spy.params.top_k == 5 * HYBRID_LEG_FACTOR

    vector_spy, keyword_spy = await _run(top_k=50)
    assert vector_spy.params.top_k == HYBRID_LEG_CAP
    assert keyword_spy.params.top_k == HYBRID_LEG_CAP


async def test_交货量仍是原始top_k():
    """腿深放大只是融合层的视野，最终交货量不受影响（空榜时为空）。"""
    retriever = HybridRetriever()
    retriever._vector, retriever._keyword = _SpyLeg(), _SpyLeg()

    result = await retriever.retrieve(None, RetrievalParams(
        query="报销要多久", top_k=5, similarity_threshold=0.6, mode=RetrievalMode.HYBRID,
    ))

    assert result.hits == []
    assert set(result.timings) == {"embed_ms", "vector_ms", "keyword_ms", "fusion_ms", "search_ms"}
