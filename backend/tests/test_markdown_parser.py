"""MarkdownParser 单测 —— 手编文本、零 DB 零 API。

守两条规矩：

1. **标题识别要准**。最大的坑不是认不出标题，而是**把代码块里的 `#` 当成
   标题**——实测本项目 43 份 md 里有 61 处，不过滤就是 11% 的假标题。
2. **切段边界不变**。第二步的契约是「只打标、不动边界」，切段规则仍与
   `PlainTextParser` 一致；边界变化留到第三步。没有这条，标题识别的效果
   就无法与切分改动分开衡量。

解码层的坑（BOM / CRLF / NUL）由 `test_text_parser.py` 覆盖，此处不重复。
"""

import pytest

from app.services.knowledge.parser.base import BlockType
from app.services.knowledge.parser.markdown_impl import MarkdownParser
from app.services.knowledge.parser.text_impl import PlainTextParser

md = MarkdownParser()
plain = PlainTextParser()


async def _parse(text: str):
    return await md.parse(text.encode("utf-8"))


async def _types(text: str) -> list[BlockType]:
    return [b.block_type for b in await _parse(text)]


# --- 标题识别 ---


@pytest.mark.parametrize("level", [1, 2, 3, 4, 5, 6])
async def test_atx_heading_levels(level: int):
    """`#` 到 `######` 六级都要认出正确层级。"""
    blocks = await _parse(f"{'#' * level} 标题\n\n正文。")
    assert blocks[0].block_type is BlockType.HEADING
    assert blocks[0].heading_level == level


@pytest.mark.parametrize(
    "line",
    [
        "#标题",  # `#` 后无空白：CommonMark 不算标题
        "####### 七级",  # 超过六级
        "    #### 缩进四空格",  # 前导空格 ≥4，CommonMark 判为缩进代码块（≤3 仍是标题）
        "文字 # 井号在中间",
        "#tag:xxx",  # 标签写法，本项目 notes 里真实存在
    ],
)
async def test_non_heading_lines_stay_paragraph(line: str):
    """长得像标题但不是的，一律归正文——认错的代价是凭空多一个层级边界。"""
    assert (await _types(f"{line}\n\n正文。"))[0] is BlockType.PARAGRAPH


async def test_bare_hash_is_heading():
    """空标题 `#` 单独一行仍是标题（CommonMark 如此规定）。"""
    assert (await _parse("#\n\n正文。"))[0].block_type is BlockType.HEADING


async def test_heading_text_keeps_hash_prefix():
    """块的 text 保留 markdown 原文含 `#`——IR 的 text 是展示形态。

    纯标题文字随时可从中取；另存一份反而会与 text 不同步。
    """
    assert (await _parse("## 3.1 向量检索\n\n正文。"))[0].text == "## 3.1 向量检索"


# --- 代码围栏（本片最大的坑） ---


async def test_hash_inside_backtick_fence_is_not_heading():
    """代码块里的 `#` 是注释不是标题——本项目 61 处真实误判来源。"""
    text = "```python\n# 这是注释\nx = 1\n```\n\n正文。"
    assert (await _types(text))[0] is BlockType.PARAGRAPH


async def test_hash_inside_tilde_fence_is_not_heading():
    """`~~~` 也是合法围栏，不能只认反引号。"""
    assert (await _types("~~~\n# 注释\n~~~\n\n正文。"))[0] is BlockType.PARAGRAPH


async def test_fence_markers_do_not_cross_match():
    """``` 与 ~~~ 不能一开一闭：错配会让围栏状态从此全篇颠倒。"""
    text = "```\n~~~\n# 仍在代码块内\n```\n\n# 真标题"
    types = await _types(text)
    assert types[0] is BlockType.PARAGRAPH
    assert types[1] is BlockType.HEADING


async def test_blank_line_inside_fence_does_not_break_state():
    """代码块内部的空行会把它切成两段，但第二段仍须知道自己在围栏里。

    这正是围栏状态必须**整篇预扫**、不能先切段再逐段判断的原因。
    """
    text = "```python\ndef a():\n    pass\n\n# 空行之后的注释\ndef b():\n    pass\n```\n\n正文。"
    assert all(t is BlockType.PARAGRAPH for t in await _types(text))


async def test_heading_after_closed_fence_recognized():
    """围栏闭合后要恢复识别，否则一个代码块就吞掉后面所有标题。"""
    text = "```\n# 注释\n```\n\n## 真标题\n\n正文。"
    assert (await _types(text))[1] is BlockType.HEADING


async def test_unclosed_fence_swallows_rest():
    """未闭合的围栏延续到文末——与 CommonMark 一致，不做补救。

    真要修也只能靠猜（猜哪里该闭合），猜错比不猜更难排查。
    """
    assert (await _types("```\n# 注释\n\n# 也在围栏内")) == [
        BlockType.PARAGRAPH,
        BlockType.PARAGRAPH,
    ]


# --- 不认 Setext ---


async def test_setext_underline_not_treated_as_heading():
    """`===` / `---` 下划线式标题不认：会与 YAML frontmatter 的收尾撞车。"""
    assert (await _types("标题\n===\n\n正文。"))[0] is BlockType.PARAGRAPH


async def test_yaml_frontmatter_stays_paragraph():
    """notes 文件的 frontmatter 必须原样留作正文，不能被判成标题。"""
    text = "---\nmodule: rag-pipeline\ntitle: RAG 工程\n---\n\n# 正文标题"
    types = await _types(text)
    assert types[0] is BlockType.PARAGRAPH
    assert types[1] is BlockType.HEADING


# --- 切段边界与 v1 一致（第二步的契约） ---


@pytest.mark.parametrize(
    "text",
    [
        "第一段\n\n第二段\n\n第三段",
        "标题下有空行\n\n# 一级\n\n正文",
        "连续空行\n\n\n\n第二段",
        "空白行分隔\n\n   \n\n第二段",
        "缩进空行不分段\n    \n仍是同一段",  # 只含空格的行不是段分隔，见下条测试
        "  首尾有空白  \n\n第二段",
        "单行无空行的文档",
        "",
    ],
)
async def test_split_boundaries_match_plain_text_parser(text: str):
    """切段结果须与 `PlainTextParser` 逐字一致——只打标、不动边界。

    实现上 MarkdownParser 按行号遍历（围栏状态是按行算的，切完段就对不
    回去），PlainTextParser 用 `split("\\n\\n")`。两条路必须等价。
    """
    raw = text.encode("utf-8")
    assert [b.text for b in await md.parse(raw)] == [
        b.text for b in await plain.parse(raw)
    ]


async def test_heading_glued_to_body_splits_into_two():
    """标题与正文之间没空行时，会从 1 段变 2 段——本片唯一有意的边界变化。

    实测本项目 2331 段里有 32 处（1.4%）。这是改进：标题本就该独立成块。
    """
    blocks = await _parse("# 标题\n正文紧跟其后。")
    assert [b.block_type for b in blocks] == [
        BlockType.HEADING,
        BlockType.PARAGRAPH,
    ]
    assert blocks[0].text == "# 标题"
    assert blocks[1].text == "正文紧跟其后。"


async def test_indented_blank_line_does_not_split_code_block():
    """代码里的缩进空行（只含空格）不是段分隔，否则一个代码块被劈两半。

    它长得像空行但不是——`split("\\n\\n")` 要求连续两个换行，而按行遍历
    若用 `line.strip()` 判空就会中招。实测本项目 3 份技术文档踩到，且这种
    变化与标题识别无关，会盖过第二步真正该看的边界变化。
    """
    text = "```python\ndef a():\n    pass\n    \n    return 1\n```"
    assert len(await _parse(text)) == 1


async def test_no_page_number_for_markdown():
    """markdown 无页码——定位信息第三步由标题链填，不是这里。"""
    assert all(b.page is None for b in await _parse("# 标题\n\n正文。"))
