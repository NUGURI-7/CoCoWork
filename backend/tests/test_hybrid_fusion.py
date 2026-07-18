"""fuse_rrf 融合纯函数单测 —— 手编榜单、零 DB 零 API。

守的规矩：等权口径（与 2026-07-18 首跑基准一字不差）、权重真的偏票、
同段跨路去重、top_k 截断、纯函数不篡改入参。分工：基准 eval 考「策略
好坏」（0.804 那种分数），这里考「实现忠实」——逻辑写错时 eval 只会
给出莫名其妙的烂分，这里毫秒级指名到函数。
"""
from uuid import UUID, uuid4

from app.schemas.knowledge import RetrievalHit
from app.services.knowledge.retrieval.hybrid import fuse_rrf


def _hit(pid: UUID, score: float, chunk_text: str = "") -> RetrievalHit:
    """手编一条命中：只有排序相关字段有讲究，其余给占位值。"""
    return RetrievalHit(
        paragraph_id=pid, document_id=uuid4(), doc_name="doc",
        content="正文", chunk_text=chunk_text, score=score,
    )


# 固定三个段位：a = 双榜第 1（共识王），b = 仅向量榜第 2，c = 仅关键词榜第 2
A, B, C = uuid4(), uuid4(), uuid4()


def _legs() -> tuple[list[RetrievalHit], list[RetrievalHit]]:
    vector_hits = [_hit(A, 0.9, chunk_text="chunk-a"), _hit(B, 0.8, chunk_text="chunk-b")]
    keyword_hits = [_hit(A, 0.7), _hit(C, 0.5)]
    return vector_hits, keyword_hits


def test_consensus_hit_tops_with_full_score():
    """双榜都第 1 的段：共识分满分 1.0、matched_by=both、chunk_text 取向量路。"""
    out = fuse_rrf(*_legs(), top_k=3)
    assert out[0].paragraph_id == A
    assert out[0].score == 1.0
    assert out[0].matched_by == "both"
    assert out[0].chunk_text == "chunk-a"


def test_equal_weight_keeps_baseline_semantics():
    """等权口径钉死：单腿第 2 名共识分 = (0.5/62)/(1/61) ≈ 0.4919，
    同分并列时向量榜先出（排序稳定性）。改动此口径 = 改动首跑基准语义。"""
    out = fuse_rrf(*_legs(), top_k=3, vector_weight=0.5)
    assert [h.paragraph_id for h in out] == [A, B, C]
    assert out[1].score == out[2].score == 0.4919
    assert out[1].matched_by == "vector"
    assert out[2].matched_by == "keyword"
    assert out[2].chunk_text == ""  # 关键词路无子块对应物


def test_vector_weight_shifts_votes():
    """w=0.9 时票权真的偏：向量单腿 (0.9/62)/(1/61)≈0.8855，
    关键词单腿 (0.1/62)/(1/61)≈0.0984 —— 数值钉死防公式漂移。"""
    out = fuse_rrf(*_legs(), top_k=3, vector_weight=0.9)
    scores = {h.paragraph_id: h.score for h in out}
    assert scores[B] == 0.8855
    assert scores[C] == 0.0984
    assert scores[A] == 1.0  # 权重和恒为 1，共识王满分不随 w 变


def test_dedup_across_legs():
    """同段在两路各出现一次，产出只有一条（按 paragraph_id 合桶）。"""
    out = fuse_rrf(*_legs(), top_k=10)
    assert len(out) == 3
    assert len({h.paragraph_id for h in out}) == 3


def test_top_k_truncates_after_ranking():
    """top_k=1 只交共识王 —— 截断发生在全量排序之后。"""
    out = fuse_rrf(*_legs(), top_k=1)
    assert [h.paragraph_id for h in out] == [A]


def test_inputs_not_mutated():
    """纯函数承诺：入参榜单的分数与 matched_by 原样无损。"""
    vector_hits, keyword_hits = _legs()
    fuse_rrf(vector_hits, keyword_hits, top_k=3)
    assert [h.score for h in vector_hits] == [0.9, 0.8]
    assert [h.score for h in keyword_hits] == [0.7, 0.5]
    assert all(h.matched_by is None for h in vector_hits + keyword_hits)


def test_empty_legs_return_empty():
    """两路全空手而归时不炸、交空榜。"""
    assert fuse_rrf([], [], top_k=5) == []
