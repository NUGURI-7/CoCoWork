"""PDF 解析（云端路）：百度文档解析 API 的 parse_result → DocumentBlock。

本模块只管**翻译**，不碰 HTTP——`parse_result` 从哪来（现调 API 还是读本地
存档）由调用方决定。好处是映射逻辑能拿存档的 JSON 直接跑，不烧解析额度。

百度返回的形状（实测确认，非文档推断）：
    {"pages": [{"page_num": 0, "layouts": [...], "tables": [...]}]}
页码从 **0** 起，标题层级是 `title_1` / `title_2` … 这类字符串。
"""

import logging
import re
from typing import Any

from app.services.knowledge.parser.base import BlockType, DocumentBlock

logger = logging.getLogger(__name__)

# 百度 layout.type → 我们的块类型。实测见过的取值：
# header / footer / number（页眉页脚页码，纯噪声，丢）
# text（正文）/ paragraph_title（标题）/ table（表格）
# figure_title（图表标题——实测在论文里全是表标题，「表2-3 粉煤灰基本性能参数」）
# vision_footnote（脚注）
#
# figure_title 与 vision_footnote 留成正文：表标题是「这张表讲什么」的唯一线索，
# 丢了下游只剩一堆裸数字；脚注同理，常含引用出处。
_TYPE_MAP: dict[str, BlockType] = {
    "text": BlockType.PARAGRAPH,
    "paragraph_title": BlockType.HEADING,
    "table": BlockType.TABLE,
    "figure_title": BlockType.PARAGRAPH,
    "vision_footnote": BlockType.PARAGRAPH,
}

# 认不出的 type 一律丢弃，而不是降级成正文——parse-don't-validate 在这里要
# 反过来用：百度的 type 是封闭枚举，冒出没见过的值多半是新的非正文元素
# （印章、水印之类），当正文收进来是污染，宁可漏不可脏。
_DROP_TYPES = frozenset({"header", "footer", "number"})

_TITLE_LEVEL = re.compile(r"^title_(\d+)$")


def _heading_level(sub_type: str) -> int | None:
    """`title_3` → 3。认不出的层级返回 None，由调用方降级处理。"""
    match = _TITLE_LEVEL.match(sub_type or "")
    return int(match.group(1)) if match else None


def _to_block(
        layout: dict[str, Any], page: int | None, table_markdowns: dict[str, str],
) -> DocumentBlock | None:
    """单个 layout → 块。该丢的返回 None。"""
    layout_type = layout.get("type", "")
    if layout_type in _DROP_TYPES:
        return None

    block_type = _TYPE_MAP.get(layout_type)
    if block_type is None:
        logger.info("跳过未登记的 layout type=%r", layout_type)
        return None

    if block_type is BlockType.TABLE:
        # 拿不到就是空串，落到下面那道空文本检查里整块丢掉——宁可少一张表，
        # 也不能把 layouts 里那坨 table_html 当正文 embed 进去
        text = table_markdowns.get(layout.get("layout_id", ""), "")
    else:
        text = layout.get("text", "")

    text = text.strip()
    if not text:
        return None

    level: int | None = None
    if block_type is BlockType.HEADING:
        level = _heading_level(layout.get("sub_type", ""))
        if level is None:
            logger.warning(
                "标题层级认不出 sub_type=%r，降级为正文：%.20s",
                layout.get("sub_type"), text,
            )
            block_type = BlockType.PARAGRAPH

    return DocumentBlock(
        text=text, block_type=block_type, heading_level=level, page=page,
    )


def blocks_from_parse_result(parsed: dict[str, Any]) -> list[DocumentBlock]:
    """百度 `parse_result` → 块列表，顺序即阅读顺序。

    `pages` 与页内 `layouts` 百度都按阅读顺序给，照单遍历即可，不必自己排。
    """
    blocks: list[DocumentBlock] = []

    for page in parsed.get("pages", []):
        # 百度的 page_num 从 0 起，IR 的 page 从 1 起
        raw_page = page.get("page_num")
        page_no = raw_page + 1 if isinstance(raw_page, int) else None

        # 表格块在 layouts 里的 text 是一坨 table_html，真正要的 markdown
        # 在同页的 tables[] 里，两边靠 layout_id 认亲
        table_markdowns = {
            table.get("layout_id", ""): table.get("markdown", "")
            for table in page.get("tables", [])
        }

        for layout in page.get("layouts", []):
            block = _to_block(layout, page_no, table_markdowns)
            if block is not None:
                blocks.append(block)

    return blocks
