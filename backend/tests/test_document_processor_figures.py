"""_persist_figures 单测 —— 存图那道工序，用假 storage、零 DB 零对象存储。

这道工序是解析器与对象存储之间的落地环节：解析器把图裁成字节塞进 meta（两阶段
合同见 parser/base.py），这里才有 kb_id / doc_id 拼 key、把字节写进存储、meta 里
image_bytes 换成 figure_key。断言三件事：key 拼对、字节原样写进存储、meta 换形正确。

storage 是 document_processor 的模块级单例，monkeypatch 掉即可拦住写出；图目录由调用方
给（每次解析一个 `figures/{uuid7}/`），这里直接传固定目录。`_new_figure_dir` 只用到 doc 的
两个属性（id / knowledge_base_id），用轻量假对象顶替，不碰 ORM 与数据库。
"""

from io import BytesIO
from types import SimpleNamespace

import pytest

from app.services.knowledge import document_processor
from app.services.knowledge.parser import BlockType, DocumentBlock


class _FakeStorage:
    """记下每次 save 的 (字节, content_type)，键是 storage key。"""

    def __init__(self) -> None:
        self.saved: dict[str, tuple[bytes, str]] = {}

    async def save(self, key, fileobj, content_type="application/octet-stream"):
        self.saved[key] = (fileobj.read(), content_type)


@pytest.fixture
def fake_storage(monkeypatch):
    fs = _FakeStorage()
    monkeypatch.setattr(document_processor, "storage", fs)
    return fs


_DIR = "kb/kbid/doc/docid/figures/p1/"


def _doc():
    """只带 _new_figure_dir 用得到的两个字段的假 doc。"""
    return SimpleNamespace(id="docid", knowledge_base_id="kbid")


def _figure_block(index: int, png: bytes) -> DocumentBlock:
    return DocumentBlock(
        text=f"[[figure:{index}]]",
        block_type=BlockType.FIGURE,
        page=1,
        meta={"image_bytes": png, "index": index, "bbox": (10.0, 20.0, 30.0, 40.0)},
    )


async def test_persist_uploads_and_rewrites_meta(fake_storage):
    """图块：字节写进存储、key 拼对、meta 里 image_bytes 换成 figure_key。"""
    block = _figure_block(1, b"PNGBYTES")
    out = await document_processor._persist_figures([block], _DIR)

    assert len(out) == 1
    fig = out[0]
    key = "kb/kbid/doc/docid/figures/p1/1.png"
    # 存储收到了原样字节，content_type 标成 png
    assert fake_storage.saved[key] == (b"PNGBYTES", "image/png")
    # meta 换形：bytes 没了，figure_key 到位，index / bbox 保留
    assert fig.meta == {"figure_key": key, "index": 1, "bbox": (10.0, 20.0, 30.0, 40.0)}
    assert "image_bytes" not in fig.meta
    # 其余字段不动
    assert fig.text == "[[figure:1]]" and fig.block_type is BlockType.FIGURE


async def test_persist_passes_non_figure_blocks_through(fake_storage):
    """非图块原样放行，不写存储。"""
    para = DocumentBlock(text="正文", block_type=BlockType.PARAGRAPH, page=1)
    out = await document_processor._persist_figures([para], _DIR)
    assert out == [para]
    assert fake_storage.saved == {}


async def test_persist_multiple_figures_keyed_by_index(fake_storage):
    """多张图各按自己的编号拼 key，互不覆盖。"""
    blocks = [_figure_block(1, b"A"), _figure_block(2, b"B")]
    await document_processor._persist_figures(blocks, _DIR)
    assert set(fake_storage.saved) == {
        "kb/kbid/doc/docid/figures/p1/1.png",
        "kb/kbid/doc/docid/figures/p1/2.png",
    }


def test_new_figure_dir_is_unique_per_parse():
    """每次解析一个新目录：落在文档目录的 figures/ 下、以 / 结尾，两次调用不重名。"""
    first = document_processor._new_figure_dir(_doc())
    second = document_processor._new_figure_dir(_doc())

    for d in (first, second):
        assert d.startswith("kb/kbid/doc/docid/figures/") and d.endswith("/")
    assert first != second
