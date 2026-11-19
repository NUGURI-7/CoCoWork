"""KB tool 出口文本的组装 —— `_format_hits`。

这是知识库检索结果**唯一**通往 LLM 的那道口子：检索层填好的 `title`
（标题链）与 `page`（PDF 页码）一直躺在 `RetrievalHit` 里、命中测试界面
也一直在显示，但此前拼给模型的那份文本只带了文档名。测试锁住的就是
「出处信息确实进了给模型的文本」，以及三种文档形态各自缺字段时不出脏串。
"""

from uuid import uuid4

from app.schemas.knowledge import RetrievalHit
from app.tools.knowledge_retrieval import _format_hits, cite_marker


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
    h = _hit(doc_name="员工手册.pdf", title="第三章 > 3.2 报销流程", page=12)
    out = _format_hits([h])

    assert out.startswith(f"## {cite_marker(h.paragraph_id)} 员工手册.pdf · 第三章 > 3.2 报销流程 · 第 12 页 · 相关度 0.87\n\n")
    # 正文原样跟在标头后面
    assert out.endswith("报销申请需在费用发生后不超过 30 天内提交。")


def test_无页码时不留空档():
    """md / txt 没有页码，出处只有文档名 + 标题链，不该冒出「第 None 页」。"""
    h = _hit(title="第三章 > 3.2 报销流程")
    out = _format_hits([h])

    assert f"## {cite_marker(h.paragraph_id)} 员工手册.md · 第三章 > 3.2 报销流程 · 相关度 0.87" in out
    assert "None" not in out


def test_无标题区域退回原行为():
    """纯 txt / md 前言这类无标题区域 title 为空串——不能拼出「文档名 ·  · 相关度」。"""
    h = _hit()
    out = _format_hits([h])

    assert f"## {cite_marker(h.paragraph_id)} 员工手册.md · 相关度 0.87" in out
    assert " ·  · " not in out


def test_页码为零照样输出():
    """0 是合法页码，不能被 falsy 判断吃掉（故判的是 `is not None`）。"""
    out = _format_hits([_hit(page=0)])

    assert "第 0 页" in out


def test_多条命中各带段引用记号且以分隔线相接():
    a, b = _hit(doc_name="A.md", title="一"), _hit(doc_name="B.md", title="二")
    out = _format_hits([a, b])

    assert f"## {cite_marker(a.paragraph_id)} A.md · 一 · " in out
    assert f"## {cite_marker(b.paragraph_id)} B.md · 二 · " in out
    assert "\n\n---\n\n" in out


def test_空命中返回空串():
    """`_execute` 在 hits 为空时会走「未找到」的分支，这里只锁住不炸。"""
    assert _format_hits([]) == ""


def test_图记号改写成跨段唯一():
    """两段都有 figure:1，改写后前缀取各自段 id 的短标识，互不相撞。"""
    from app.core.identifiers import short_id

    a = _hit(content="流程如下：\n\n[[figure:1]]\n\n第三步")
    b = _hit(content="[[figure:1]]\n\n[[figure:2]]")
    out = _format_hits([a, b])

    pa, pb = short_id(a.paragraph_id), short_id(b.paragraph_id)
    assert f"[[figure:{pa}-1]]" in out
    assert f"[[figure:{pb}-1]]" in out
    assert f"[[figure:{pb}-2]]" in out
    # 段内原始写法不再出现
    assert "[[figure:1]]" not in out


def test_引用记号取段id后8位():
    """记号格式是前端查表的约定，取后 8 位（随机段）而非前 8 位（时间戳）。"""
    from uuid import UUID

    pid = UUID("0190a1b2-c3d4-7e5f-8a9b-0c1d2e3f4a5b")
    assert cite_marker(pid) == "[[cite:2e3f4a5b]]"


async def test_工具返回正文与命中段id():
    """content_and_artifact：出错 / 超时路径也必须回二元组，artifact 为 None。"""
    from unittest.mock import patch

    from app.tools.knowledge_retrieval import KnowledgeRetrievalTool

    tool = KnowledgeRetrievalTool.model_construct(
        name="knowledge_x", description="d", display_name="知识库", kb_id=uuid4(), user=None,
        default_top_k=3, response_format="content_and_artifact", timeout_seconds=5.0,
        max_output_chars=4000,
    )
    with patch(
        "app.tools.knowledge_retrieval._retrieval_service.retrieve",
        side_effect=RuntimeError("boom"),
    ):
        content, artifact = await tool._arun(query="q")
    assert "执行出错" in content
    assert artifact is None


async def test_附带数据的ref与正文里的引用记号一致():
    """前端拿回答里的 [[cite:x]] 去 hits 里按 ref 查——两边必须同源。"""
    from unittest.mock import patch

    from app.services.knowledge.retrieval.base import RetrievalResult
    from app.tools.knowledge_retrieval import KnowledgeRetrievalTool

    h = _hit(doc_name="员工手册.pdf", title="第三章", page=3, content="见下图\n\n[[figure:1]]")
    tool = KnowledgeRetrievalTool.model_construct(
        name="knowledge_x", description="d", display_name="知识库", kb_id=uuid4(), user=None,
        default_top_k=3, response_format="content_and_artifact", timeout_seconds=5.0,
        max_output_chars=4000,
    )
    with patch(
        "app.tools.knowledge_retrieval._retrieval_service.retrieve",
        return_value=RetrievalResult(hits=[h]),
    ):
        content, artifact = await tool._arun(query="q")

    ref = artifact.hits[0]
    assert f"[[cite:{ref.ref}]]" in content
    assert (ref.paragraph_id, ref.doc_name, ref.title, ref.page) == (h.paragraph_id, "员工手册.pdf", "第三章", 3)
    # 弹窗原文用的是改写过插图记号的版本，前端可复用插图渲染
    assert "[[figure:1]]" not in ref.content
    assert artifact.paragraph_ids == [h.paragraph_id]
