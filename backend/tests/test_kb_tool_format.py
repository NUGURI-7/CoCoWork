"""KB tool 出口文本的组装 —— `_format_hits`。

这是知识库检索结果**唯一**通往 LLM 的那道口子：检索层填好的 `title`
（标题链）与 `page`（PDF 页码）一直躺在 `RetrievalHit` 里、命中测试界面
也一直在显示，但此前拼给模型的那份文本只带了文档名。测试锁住的就是
「出处信息确实进了给模型的文本」，以及三种文档形态各自缺字段时不出脏串。
"""

from uuid import uuid4

from app.schemas.knowledge import RetrievalHit
from app.tools.knowledge_retrieval import _format_hits


def _hit(**kwargs) -> RetrievalHit:
    """造一条命中，只覆盖关心的字段。"""
    base = dict(
        paragraph_id=uuid4(),
        document_id=uuid4(),
        doc_name="员工手册.md",
        content="报销申请需在费用发生后不超过 30 天内提交。",
        chunk_text="不超过 30 天",
        score=0.87,
    )
    return RetrievalHit(**{**base, **kwargs})


def test_出处含标题链与页码():
    """PDF 命中：文档名 + 标题链 + 页码 + 相关度，四段用 · 串起来。"""
    out = _format_hits([
        _hit(doc_name="员工手册.pdf", title="第三章 > 3.2 报销流程", page=12),
    ])

    assert out.startswith("## [1] 员工手册.pdf · 第三章 > 3.2 报销流程 · 第 12 页 · 相关度 0.87\n\n")
    # 正文原样跟在标头后面
    assert out.endswith("报销申请需在费用发生后不超过 30 天内提交。")


def test_无页码时不留空档():
    """md / txt 没有页码，出处只有文档名 + 标题链，不该冒出「第 None 页」。"""
    out = _format_hits([_hit(title="第三章 > 3.2 报销流程")])

    assert "## [1] 员工手册.md · 第三章 > 3.2 报销流程 · 相关度 0.87" in out
    assert "None" not in out


def test_无标题区域退回原行为():
    """纯 txt / md 前言这类无标题区域 title 为空串——不能拼出「文档名 ·  · 相关度」。"""
    out = _format_hits([_hit()])

    assert "## [1] 员工手册.md · 相关度 0.87" in out
    assert " ·  · " not in out


def test_页码为零照样输出():
    """0 是合法页码，不能被 falsy 判断吃掉（故判的是 `is not None`）。"""
    out = _format_hits([_hit(page=0)])

    assert "第 0 页" in out


def test_多条命中按序编号且以分隔线相接():
    out = _format_hits([
        _hit(doc_name="A.md", title="一"),
        _hit(doc_name="B.md", title="二"),
    ])

    assert "## [1] A.md · 一 · " in out
    assert "## [2] B.md · 二 · " in out
    assert "\n\n---\n\n" in out


def test_空命中返回空串():
    """`_execute` 在 hits 为空时会走「未找到」的分支，这里只锁住不炸。"""
    assert _format_hits([]) == ""
