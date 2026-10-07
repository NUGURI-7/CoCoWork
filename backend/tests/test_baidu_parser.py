"""百度云端解析的翻译层：layout → 块。不调百度，parse_result 手编、PDF 手搓。"""
from io import BytesIO

import pdfplumber
from PIL import Image

from app.services.knowledge.parser import figure_marker
from app.services.knowledge.parser.baidu_impl import _layout_bbox, blocks_from_parse_result
from app.services.knowledge.parser.base import BlockType
from tests.test_pdf_parser import _pdf_with_partial_image

# 手搓 PDF：400x300 的页，(150,120)-(250,180) 夹一张纯红位图
PDF = _pdf_with_partial_image()
PAGE_META = {"page_width": 400, "page_height": 300}


def _layout(type_: str, *, text: str = "", sub_type: str = "", position=None) -> dict:
    return {"type": type_, "sub_type": sub_type, "text": text, "position": [0, 0, 1, 1] if position is None else position}


def _parsed(*layouts: dict, page_num: int = 0) -> dict:
    return {"pages": [{"page_num": page_num, "meta": PAGE_META, "layouts": list(layouts), "tables": []}]}


def test_doc_title_becomes_level_one_heading():
    blocks = blocks_from_parse_result(_parsed(_layout("doc_title", text="大标题")), PDF)

    assert len(blocks) == 1
    assert blocks[0].block_type is BlockType.HEADING
    assert blocks[0].heading_level == 1


def test_header_image_is_dropped():
    blocks = blocks_from_parse_result(
        _parsed(_layout("header_image"), _layout("text", text="正文")), PDF,
    )

    assert [b.text for b in blocks] == ["正文"]


def test_image_layout_becomes_cropped_figure():
    blocks = blocks_from_parse_result(
        _parsed(_layout("image", position=[150, 120, 100, 60])), PDF,
    )

    assert len(blocks) == 1
    figure = blocks[0]
    assert figure.block_type is BlockType.FIGURE
    assert figure.text == figure_marker(1)
    assert figure.page == 1
    assert figure.meta["index"] == 1
    assert figure.meta["bbox"] == (150, 120, 250, 180)
    # 截出来的就是那张红图：取中心像素
    image = Image.open(BytesIO(figure.meta["image_bytes"])).convert("RGB")
    r, g, b = image.getpixel((image.width // 2, image.height // 2))
    assert r > 200 and g < 50 and b < 50


def test_invalid_figure_does_not_consume_index():
    blocks = blocks_from_parse_result(
        _parsed(
            _layout("image", position=[]),  # 坐标缺失 → 跳过
            _layout("image", position=[150, 120, 100, 60]),
        ),
        PDF,
    )

    assert [b.meta["index"] for b in blocks] == [1]
    assert blocks[0].text == figure_marker(1)


def test_figure_on_page_beyond_pdf_is_skipped():
    blocks = blocks_from_parse_result(
        _parsed(_layout("image", position=[150, 120, 100, 60]), page_num=5), PDF,
    )

    assert blocks == []


def _pdf_page():
    return pdfplumber.open(BytesIO(PDF)).pages[0]


def test_layout_bbox_scales_to_pdf_size():
    """百度按 800x600 记坐标、PDF 实际 400x300 → 坐标减半。"""
    bbox = _layout_bbox(
        {"position": [300, 240, 200, 120]}, {"page_width": 800, "page_height": 600}, _pdf_page(),
    )

    assert bbox == (150, 120, 250, 180)


def test_layout_bbox_without_page_size_uses_pdf_units():
    bbox = _layout_bbox({"position": [150, 120, 100, 60]}, {}, _pdf_page())

    assert bbox == (150, 120, 250, 180)


def test_layout_bbox_clamped_to_page():
    bbox = _layout_bbox({"position": [350, 250, 100, 100]}, PAGE_META, _pdf_page())

    assert bbox == (350, 250, 400, 300)


def test_layout_bbox_invalid_returns_none():
    page = _pdf_page()

    assert _layout_bbox({}, PAGE_META, page) is None
    assert _layout_bbox({"position": [1, 2, 3]}, PAGE_META, page) is None
    assert _layout_bbox({"position": [500, 400, 10, 10]}, PAGE_META, page) is None  # 整框在页外
