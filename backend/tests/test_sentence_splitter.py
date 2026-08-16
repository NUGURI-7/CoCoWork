"""SentenceSplitter 单测 —— 纯内存、零 DB 零 API（tiktoken 编码表走本地缓存）。

这一层为什么值得单测：它**带状态**且**有三条互相拉扯的约束**。`cur` / `cur_tokens`
跨循环轮次累积，而每一轮要同时满足「块不超上限」「切口落在句末」「overlap 垫得
进去」——三者冲突时的优先级是写在代码里的隐式决策，读代码读不出来。

而且它错了**不报错**：块切大了照样能 embed（模型静默截断）、切口劈了句子照样
能算出向量，整条流水线一路绿到 completed，只有翻数据库才看得见。

四类断言：

1. **硬上限**（`chunk_size` 是对用户的承诺）——唯一绝不能破的约束，
   所以 overlap 与它冲突时必须让路，这条要专门测。
2. **切口在句末标点**——整个实现存在的理由。只有 `_hard_split` 那条兜底
   路径例外。
3. **原文可还原**（overlap=0 时逐字拼回）——`Embedding.text` 要拿它定位回
   段落原文，断句时丢了空白就对不上了。
4. **overlap 的「至少覆盖」语义**——回归界碑。这里曾按「不超过 overlap」
   实现，配上中文句子普遍 25~50 token 的现实，等于让这个参数永远失效。

`chunk_size` 用 30~40 的小值而非默认 128：造一百多 token 的样本只会让用例读不
懂，而该函数把上限做成参数本就是为了可调。
"""

import pytest

from app.schemas.knowledge import ChunkConfig
from app.services.knowledge.splitter.sentence_impl import (
    SentenceSplitter,
    _count,
    _split_sentences,
)

# 样本句。注释里的 token 数是 cl100k_base 实测值，用例的临界点依赖它们
S1 = "这是第一句话。"                                # 8
S2 = "生产环境一般选 HNSW。"                          # 13
S3 = "好的。"                                        # 3
S4 = "它支持 HNSW 和 IVFFlat 两种索引方式，各有取舍。"  # 25

splitter = SentenceSplitter()


def cfg(size: int, overlap: int = 0) -> ChunkConfig:
    """跳过 pydantic 校验直接构造 —— `chunk_size` 的下限是 128，而用例要的是
    30~60 这种能一眼数清的小值。这里测的是切块行为，不是 schema 的约束。
    """
    return ChunkConfig.model_construct(chunk_size=size, overlap=overlap)


# --- 前提：样本的 token 数得跟注释对得上，否则下面所有临界点都失去意义 ---

def test_sample_token_counts():
    assert (_count(S1), _count(S2), _count(S3), _count(S4)) == (8, 13, 3, 25)


# --- 1. 硬上限 ---

def test_never_exceeds_chunk_size():
    text = S1 + S2 + S3 + S4 + S1 + S2 + S4
    for size in (30, 40, 60):
        for overlap in (0, 10, 20):
            chunks = splitter.split(text, cfg(size, overlap))
            assert chunks, f"size={size} overlap={overlap} 切了个空"
            for c in chunks:
                assert _count(c) <= size, f"size={size} overlap={overlap} 超限：{c!r}"


def test_overlap_yields_to_chunk_size():
    """尾巴 + 下一句超限时，尾巴让路 —— 上限优先。

    size=30 时：块1=S1+S2(21)，封口后垫回 S2(13)，而下一句 S4 是 25，
    13+25=38 已破 30，故尾巴必须整个丢掉，块2 只有 S4。
    """
    chunks = splitter.split(S1 + S2 + S4, cfg(30, overlap=10))
    assert chunks[-1] == S4


# --- 2. 切口落在句末标点 ---

def test_cuts_land_on_sentence_ends():
    text = S1 + S2 + S3 + S4 + S1 + S2
    chunks = splitter.split(text, cfg(30))
    # 末块是攒到没句子了才封的，不要求以标点收尾
    for c in chunks[:-1]:
        assert c.rstrip()[-1] in "。！？；!?;", f"切口劈在句中：{c!r}"


# --- 3. 原文可还原 ---

@pytest.mark.parametrize("text", [
    S1 + S2 + S3 + S4,
    "第一句。第二句！\n\n第三句没有标点",
    "问：这样行吗？答：可以。\n下一段继续。",
])
def test_roundtrip_without_overlap(text):
    """overlap=0 时，子块逐字拼回必须等于原文。

    断句时若把纯空白片段 strip 掉，这条就会挂 —— 而它挂了意味着
    `Embedding.text` 再也无法定位回段落原文。
    """
    assert "".join(splitter.split(text, cfg(60))) == text


def test_split_sentences_roundtrip():
    text = "甲。\n\n乙！\n丙？   \n\n丁"
    assert "".join(_split_sentences(text)) == text


# --- 4. overlap 的「至少覆盖」语义 ---

def test_overlap_carries_whole_sentence():
    """overlap=10 而末句 13 token：按「至少覆盖」应当带上整句。

    size=40 时：块1=S1+S2(21)，封口垫回 S2(13)，13+25=38 未破 40，
    故 S2 同时出现在两块里。
    """
    chunks = splitter.split(S1 + S2 + S4, cfg(40, overlap=10))
    assert len(chunks) == 2
    assert S2 in chunks[0]
    assert chunks[1].startswith(S2)


def test_overlap_skips_oversized_tail():
    """末句本身超过硬顶（半块）时一句都不带 —— 垫进去下一块开局就废大半。

    size=30 → limit=15，而 S4 是 25：块2 封口后不该往块3 里垫任何东西。
    """
    chunks = splitter.split(S1 + S4 + S2, cfg(30, overlap=10))
    assert chunks[-1] == S2


def test_zero_overlap_never_repeats():
    chunks = splitter.split(S1 + S2 + S4 + S1 + S3, cfg(30, overlap=0))
    assert "".join(chunks) == S1 + S2 + S4 + S1 + S3


# --- 5. 边角 ---

def test_empty_text():
    assert splitter.split("", cfg(30)) == []


def test_short_text_stays_whole():
    text = S1 + S2 + S3
    assert splitter.split(text, cfg(60)) == [text]


def test_hard_split_on_unpunctuated_run():
    """无标点长文没有下刀点，只能按 token 均分 —— 唯一会切断句子的路径。"""
    text = "啊" * 300
    chunks = splitter.split(text, cfg(30))
    assert len(chunks) > 1
    for c in chunks:
        assert _count(c) <= 30
