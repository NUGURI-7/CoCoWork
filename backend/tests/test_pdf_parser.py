"""PdfParser 单测 —— 纯函数用手编数据，整份解析用 `data/pdf/` 的真实语料。

分两半，理由不同：

- **纯函数**（判定、分档、合并、转换）手编 `_Line` 直接调，零 IO、零 PDF。
  阈值类逻辑的坑都在边界上，手编数据才造得出「差一点点」的用例。
- **整份解析**跑真 PDF。字号启发式的每条规则都是看真实分布定的，脱离真实
  文档的断言证明不了什么——`_running_heads` 靠跨页重复、`_merge_paragraphs`
  靠页右边界，这些在合成数据里都是自说自话。

语料在仓库根 `data/pdf/` 且**不进 git**（体积大、含他人版权文档）。缺了就
`skipif` 跳过而不是红——本地跑得到真断言，别人 clone 下来也不会一片失败。
换语料时连同 `scripts/probe_pdfplumber.py` 一起重跑，阈值可能要重定。

已知限制写成 `xfail(strict=True)` 而非注释：限制是会变的，写成可执行的记录，
哪天真修好了测试会立刻变红提醒删掉标记；写在注释里只会烂在那儿。
"""

from pathlib import Path

import pytest

from app.services.knowledge.assembler import assemble_paragraphs
from app.services.knowledge.parser.base import BlockType
from app.services.knowledge.parser.pdf_impl import (
    PdfParser,
    _body_size,
    _cover_pages,
    _group_lines,
    _heading_levels,
    _in_any_box,
    _is_bold,
    _is_toc_line,
    _is_toc_page,
    _join_continuation,
    _Line,
    _merge_paragraphs,
    _normalize,
    _running_heads,
    _table_to_markdown,
)


def line(
    text: str = "正文",
    size: float = 12.0,
    bold: bool = False,
    top: float = 100.0,
    x0: float = 50.0,
    x1: float = 500.0,
    page: int = 1,
) -> _Line:
    """造一行。默认值就是「一行普通正文」，测哪个特征就只改哪个参数。"""
    return _Line(text=text, size=size, bold=bold, top=top, x0=x0, x1=x1, page=page)


def char(
    text: str,
    size: float = 12.0,
    fontname: str = "SimSun",
    x0: float = 50.0,
    x1: float = 60.0,
    top: float = 100.0,
) -> dict:
    """造一个 pdfplumber 风格的字符 dict（只带 `_group_lines` 用得到的键）。"""
    return {"text": text, "size": size, "fontname": fontname, "x0": x0, "x1": x1, "top": top}


# --- 目录行 / 目录页判定 ---


@pytest.mark.parametrize(
    "text",
    [
        "第一章 绪论 ....................... 1",
        "1.2.1泡沫的生成与稳定机制..............",
        "摘 要 ······ Ⅰ",  # 间隔号 U+00B7 做引导符
        "参考文献 ………… 36",  # 省略号 U+2026 ×4
    ],
)
def test_toc_line_recognized(text: str):
    """点号引导线是目录条目的标志，各家模板用的符号不同，都要认。"""
    assert _is_toc_line(text)


@pytest.mark.parametrize(
    "text",
    [
        "Well... maybe not",  # 英文省略号正好三个点，正文里满地都是
        "他说……然后走了",  # 中文省略号是两个 U+2026，够不到 4
        "1.2.3 小节标题",  # 编号里的点被数字隔开，不成串
        "第一章 绪论",
    ],
)
def test_non_toc_line(text: str):
    """门槛定在 4 个连续点，就是为了放过这些。"""
    assert not _is_toc_line(text)


def test_toc_page_over_ratio():
    """一页里过半是目录条目 → 整页判为目录。"""
    lines = [line(text=f"第{i}章 ......... {i}") for i in range(3)]
    lines += [line(text="目 录"), line(text="青岛理工大学毕业设计(论文)")]
    assert _is_toc_page(lines)  # 3/5 = 0.6


def test_toc_page_under_ratio():
    """不过半就不是——正文里偶尔出现分隔线不该拖累整页。"""
    lines = [line(text=f"标题 ........ {i}") for i in range(2)]
    lines += [line(text="正文") for _ in range(3)]
    assert not _is_toc_page(lines)  # 2/5 = 0.4


def test_toc_page_needs_min_lines():
    """整页都是目录行但只有 4 行：行数不够不判，防稀疏页被一行毙掉。"""
    assert not _is_toc_page([line(text="标题 ........ 1") for _ in range(4)])


def test_toc_page_empty():
    assert not _is_toc_page([])


# --- 封面页判定 ---


def cover_lines(page: int = 1) -> list[_Line]:
    """一页典型封面：全是大字号，没有一行是正文字号。"""
    return [
        line(text="青岛理工大学", size=42.0, page=page),
        line(text="毕业设计论文", size=42.0, page=page),
        line(text="气泡在水泥浆早期水化过程演变规律", size=24.0, page=page),
        line(text="学生姓名：张展玮", size=15.0, page=page),
        line(text="2025年 6月 16 日", size=14.0, page=page),
    ]


def test_cover_page_detected():
    assert _cover_pages(cover_lines(), body_size=12.0) == {1}


def test_cover_page_rejected_when_body_text_present():
    """有正文字号的行 = 这页有正文 = 不是封面。挡的是普通正文页。"""
    assert _cover_pages(cover_lines() + [line(size=12.0)], body_size=12.0) == set()


def test_cover_page_rejected_when_not_big_enough():
    """字号没到正文的 1.5 倍：实测学位论文的图注页只有 0.88 倍，同样没有正文字号行。"""
    lines = [line(text=f"图 {i}-1 说明", size=10.6) for i in range(5)]
    assert _cover_pages(lines, body_size=12.0) == set()


def test_cover_page_rejected_when_too_many_lines():
    """双栏期刊首页：1.97 倍、无正文字号行，前两条全中，只有行数拦得住。"""
    lines = [line(text=f"第 {i} 行", size=19.7) for i in range(21)]
    assert _cover_pages(lines, body_size=10.0) == set()


def test_cover_pages_judged_per_page():
    """判定按页独立，封面命中不牵连正文页。"""
    lines = cover_lines(page=1) + [line(size=12.0, page=2)]
    assert _cover_pages(lines, body_size=12.0) == {1}


# --- 正文字号与标题层级 ---


def test_body_size_counts_lines_not_chars():
    """按行数不按字符数——实测双栏交错时 7.6pt 每行 80 字，字符总量会反超正文，
    基准一错，几百行正文全被判成标题。"""
    lines = [line(text="x" * 80, size=7.6) for _ in range(2)]
    lines += [line(text="短", size=10.0) for _ in range(3)]
    assert _body_size(lines) == 10.0


def test_body_size_empty():
    assert _body_size([]) == 0.0


def test_heading_levels_ordered_by_size():
    """字号大的层级高（层级 1 起），正文字号不加粗的不进表。"""
    lines = [line(size=16.0, bold=True), line(size=14.0, bold=True), line(size=12.0)]
    assert _heading_levels(lines, body_size=12.0) == {(16.0, True): 1, (14.0, True): 2}


def test_heading_levels_same_size_bold_ranks_higher():
    """同字号加粗算更高一档——assembler 的 `_push` 靠层级出栈，两者必须分得开。"""
    lines = [line(size=14.0, bold=True), line(size=14.0, bold=False)]
    assert _heading_levels(lines, body_size=12.0) == {(14.0, True): 1, (14.0, False): 2}


def test_heading_levels_bold_at_body_size_is_heading():
    """正文字号 + 加粗也算标题：测试文档的一级标题只比正文大 1pt，
    MaxKB 那种「大 2pt 才算标题」的纯字号阈值会全漏，全靠字重救回来。"""
    assert (12.0, True) in _heading_levels([line(size=12.0, bold=True)], body_size=12.0)


def test_heading_levels_smaller_than_body_is_not_heading():
    """比正文小的一律不是标题——10pt 引注块就是这么被放过的。"""
    assert _heading_levels([line(size=10.0, bold=True)], body_size=12.0) == {}


# --- 页眉页脚 ---


def test_running_head_needs_two_pages():
    """同高 + 同文 + 跨 2 页 = 页眉页脚。取 2 而非过半：期刊常奇偶页页眉不同。"""
    lines = [line(text="刊名", top=40.0, page=1), line(text="刊名", top=40.0, page=2)]
    assert (40.0, "刊名") in _running_heads(lines)


def test_single_page_line_is_not_running_head():
    """只出现一页的不是页眉——真标题不会在多页同一高度重复。"""
    assert _running_heads([line(text="第一章 绪论", top=40.0)]) == set()


def test_running_head_tolerates_top_jitter():
    """同一页眉在各页的 top 会抖零点几，量化到 5pt 桶里才对得上。"""
    lines = [line(text="刊名", top=40.0, page=1), line(text="刊名", top=41.2, page=2)]
    assert len(_running_heads(lines)) == 1


def test_same_text_far_apart_is_not_running_head():
    """位置差太远就不算——正文里重复出现的短句不该被当页眉丢掉。"""
    lines = [line(text="本章小结", top=40.0, page=1), line(text="本章小结", top=400.0, page=2)]
    assert _running_heads(lines) == set()


# --- 段落合并 ---


def test_full_line_continues_paragraph():
    """上一行写到了页右边界 = 被排版截断 = 下一行是它的续行。"""
    lines = [line(text="第一行", x1=500.0), line(text="第二行", x1=500.0)]
    assert _merge_paragraphs(lines, body_size=12.0) == [("第一行第二行", 1)]


def test_short_line_ends_paragraph():
    """上一行没写满 = 段末，再下一行开新段。"""
    lines = [
        line(text="满行", x1=500.0),
        line(text="段末短行", x1=300.0),
        line(text="新段", x1=500.0),
    ]
    assert _merge_paragraphs(lines, body_size=12.0) == [("满行段末短行", 1), ("新段", 1)]


def test_indent_starts_new_paragraph():
    """首行缩进强制开新段——补的是「上一段正好写满最后一行」时满行信号的漏。"""
    lines = [
        line(text="上一段", x0=50.0),
        line(text="缩进新段", x0=80.0),
        line(text="其续行", x0=50.0),
    ]
    assert _merge_paragraphs(lines, body_size=12.0) == [("上一段", 1), ("缩进新段其续行", 1)]


def test_paragraph_continues_across_pages():
    """右边界按页算，故跨页续行天然成立；段的页码记**起始页**。"""
    lines = [line(text="上页末行", x1=500.0, page=1), line(text="下页首行", x1=400.0, page=2)]
    assert _merge_paragraphs(lines, body_size=12.0) == [("上页末行下页首行", 1)]


def test_merge_paragraphs_empty():
    assert _merge_paragraphs([], body_size=12.0) == []


@pytest.mark.parametrize(
    ("head", "tail", "expected"),
    [
        ("中文", "续行", "中文续行"),
        ("cementitious", "materials", "cementitious materials"),  # 换行处 PDF 不存空格
        ("中文", "abc", "中文abc"),  # 中西交界本就无空格
        ("abc", "中文", "abc中文"),
        ("", "abc", "abc"),
    ],
)
def test_join_continuation(head: str, tail: str, expected: str):
    assert _join_continuation(head, tail) == expected


# --- 表格转 markdown ---


def test_table_to_markdown_basic():
    """首行当表头。转 markdown 而非制表符对齐：LLM 对前者的理解明显更好。"""
    assert _table_to_markdown([["模块", "输入"], ["层级推断", "字号"]]) == (
        "| 模块 | 输入 |\n|---|---|\n| 层级推断 | 字号 |"
    )


def test_table_none_cell_becomes_empty():
    """`extract_tables()` 的空单元格给 None，直接拼会写出 "None"。"""
    assert _table_to_markdown([["a", "b"], ["1", None]]).endswith("| 1 |  |")


def test_table_ragged_rows_padded():
    """合并单元格会让各行列数不齐，统一补齐到最宽那行。"""
    assert _table_to_markdown([["a", "b", "c"], ["1"]]).splitlines()[-1] == "| 1 |  |  |"


def test_table_pipe_escaped():
    """单元格里的 `|` 不转义会把表格结构撑烂。"""
    assert "\\|" in _table_to_markdown([["a|b"]])


def test_table_newline_flattened():
    """单元格内换行要压平，否则一个单元格能把整张表拆成好几行。"""
    assert _table_to_markdown([["第一行\n第二行"]]).startswith("| 第一行 第二行 |")


def test_table_empty():
    assert _table_to_markdown([]) == ""
    assert _table_to_markdown([[]]) == ""


# --- 字符层：归一化 / 字重 / 表格框 / 聚行 ---


def test_normalize_kangxi_radical():
    """康熙部首 `⼀`(U+2F00) 与汉字 `一` 不是同一个码位，不归一化就永远匹配不上。"""
    assert _normalize("⼀般") == "一般"


def test_normalize_keeps_fullwidth_punctuation():
    """全角标点原样保留——整段 NFKC 会把它转半角，那是改原文。"""
    assert _normalize("（中文），。") == "（中文），。"


def test_normalize_leaves_unmappable_radical():
    """CJK 部首补充段（`⻚`）没有兼容映射，NFKC 也修不了，原样留着。"""
    assert _normalize("⻚") == "⻚"


@pytest.mark.parametrize(
    ("fontname", "expected"),
    [
        ("ABCDEF+SimHei-Bold", True),
        ("Arial-Black", True),
        ("XXXXXX+Helvetica-SemiBold", True),
        ("Times-Roman", False),
        ("SimSun", False),
    ],
)
def test_is_bold(fontname: str, expected: bool):
    """字重只能从字体名猜——PDF 没有独立的 weight 字段。"""
    assert _is_bold(fontname) is expected


def test_in_any_box():
    """表格区域的字符必须先剔掉，否则正文与 markdown 表格里各出现一遍。"""
    box = [(0.0, 0.0, 100.0, 100.0)]
    assert _in_any_box(char("字", x0=10.0, top=20.0), box)
    assert not _in_any_box(char("字", x0=200.0, top=20.0), box)
    assert not _in_any_box(char("字", x0=10.0, top=20.0), [])


def test_group_lines_by_top():
    chars = [char("一", x0=50.0), char("行", x0=60.0), char("下", top=200.0)]
    assert [ln.text for ln in _group_lines(chars, 1)] == ["一行", "下"]


def test_group_lines_size_is_mode_not_average():
    """行内混着上标时取众数——取平均会算出文档里根本不存在的字号档，后面分档全歪。"""
    chars = [char("正", size=10.0), char("文", size=10.0), char("字", size=10.0)]
    chars.append(char("1", size=6.0))
    assert _group_lines(chars, 1)[0].size == 10.0


def test_group_lines_tolerates_top_jitter():
    """同行内大小字的 top 会微差，要求严格相等会把一行拆成两行。"""
    chars = [char("大", size=16.0, top=100.0), char("小", size=10.0, top=101.5)]
    assert len(_group_lines(chars, 1)) == 1


def test_group_lines_drops_blank():
    assert _group_lines([char("  ")], 1) == []


# --- 真语料（gitignored，缺了就跳过） ---

CORPUS = Path(__file__).resolve().parents[2] / "data" / "pdf"
THESIS = CORPUS / "00059.pdf"  # 学位论文 54 页，单栏，有封面 / 目录 / 旋转表
SYNTHETIC = CORPUS / "PDF结构测试文档.pdf"  # 合成样本，附答案表
JOURNAL = CORPUS / "qipao.pdf"  # 期刊论文，双栏（本地路不支持）


def requires(pdf: Path):
    """语料缺失时跳过而非失败——`data/` 不进 git，别人 clone 下来没有。"""
    return pytest.mark.skipif(not pdf.exists(), reason=f"语料缺失：{pdf}")


@pytest.fixture(scope="module")
def thesis_blocks():
    """解析一次全模块复用——54 页要跑几秒。`_parse_sync` 是同步实现，
    直接调可以让 fixture 不必是 async 的。"""
    return PdfParser._parse_sync(THESIS.read_bytes())


@pytest.fixture(scope="module")
def synthetic_blocks():
    return PdfParser._parse_sync(SYNTHETIC.read_bytes())


@requires(THESIS)
def test_thesis_toc_pages_dropped(thesis_blocks):
    """目录页整页丢弃：不留任何带点号引导线的块。

    不丢的话，用户搜「第一章 绪论」命中的是目录里那行 `第一章 绪论 ....... 1`。
    """
    assert not [b for b in thesis_blocks if _is_toc_line(b.text)]


@requires(THESIS)
def test_thesis_cover_kept_as_one_paragraph(thesis_blocks):
    """封面降级为正文而非整页丢弃：论文题目只在封面出现这一次，丢了就再也搜不到。

    且必须是**一块**——逐行进正文流程的话题目会被折行切成两段。
    """
    first = thesis_blocks[0]
    assert first.block_type is BlockType.PARAGRAPH
    assert first.page == 1
    assert "气泡在水泥浆早期水化过程演变规律" in first.text


@requires(THESIS)
def test_thesis_cover_not_in_title_chain(thesis_blocks):
    """封面不再产标题，故没有一条标题链带着封面残片。

    修之前每一段的链都形如 `( ) > 研究 > 第三章 …`：封面 42pt 被判成 H1、
    之后再没有同级标题把它挤出栈。
    """
    titles = {d.title for d in assemble_paragraphs(thesis_blocks)}
    assert not [t for t in titles if "( )" in t]


@requires(THESIS)
def test_thesis_chapter_ranks_above_section(thesis_blocks):
    """章比节高一级——标题链的父子关系正确与否全看这个。"""
    levels = {
        b.text: b.heading_level
        for b in thesis_blocks
        if b.block_type is BlockType.HEADING
    }
    assert levels["第一章 绪论"] < levels["1.1研究背景及意义"]


@requires(THESIS)
def test_thesis_rotated_page_dropped(thesis_blocks):
    """p54 是竖排的评价表，按 y 坐标聚行会每字一行、顺序全乱，整页剔除。"""
    assert 54 not in {b.page for b in thesis_blocks}


@requires(SYNTHETIC)
@pytest.mark.parametrize("title", ["一、绪论", "二、方法", "三、结论"])
def test_synthetic_one_pt_heading_recognized(synthetic_blocks, title: str):
    """一级标题只比正文大 1pt（13 vs 12），纯字号阈值必漏，全靠字重救回来。"""
    headings = {b.text for b in synthetic_blocks if b.block_type is BlockType.HEADING}
    assert title in headings


@requires(SYNTHETIC)
def test_synthetic_quote_block_is_not_heading(synthetic_blocks):
    """10pt 引注块比正文小，不能因为「字号偏离正文」就判成标题。"""
    quotes = [b for b in synthetic_blocks if b.text.startswith("注：")]
    assert quotes
    assert all(b.block_type is BlockType.PARAGRAPH for b in quotes)


@requires(SYNTHETIC)
def test_synthetic_table_is_own_block(synthetic_blocks):
    """表格独立成块并转 markdown，不被打散成一行行正文。"""
    tables = [b for b in synthetic_blocks if b.block_type is BlockType.TABLE]
    assert len(tables) == 1
    assert "| 模块 | 输入 | 输出 |" in tables[0].text


@requires(SYNTHETIC)
def test_synthetic_table_header_is_not_heading(synthetic_blocks):
    """表头是「正文字号 + 加粗」，正撞标题规则；靠先剔掉表格区域的字避开。"""
    headings = {b.text for b in synthetic_blocks if b.block_type is BlockType.HEADING}
    assert "模块" not in headings


@requires(SYNTHETIC)
def test_synthetic_footer_filtered(synthetic_blocks):
    """页脚 10pt 逼近正文 12pt，靠字号过滤必错，只能靠「同高同文跨页重复」。"""
    assert not [b for b in synthetic_blocks if "Internal Use Only" in b.text]


@requires(SYNTHETIC)
def test_synthetic_cross_page_paragraph_merged(synthetic_blocks):
    """跨页段落合并：p3 开头那句并进了起始于 p2 的段落，没有按页被切开。"""
    assert [
        b for b in synthetic_blocks if b.page == 2 and "综上，本文档已覆盖" in b.text
    ]


@requires(SYNTHETIC)
@pytest.mark.xfail(
    strict=True,
    reason="字号推层级的固有失效面：本文档 H1=13pt < H2=16pt（答案表明说是刻意造的"
    "陷阱）。排版不规范的文档明确不处理，真层级走云端路拿 sub_type（设计稿 D4）",
)
def test_synthetic_heading_level_matches_numbering(synthetic_blocks):
    levels = {
        b.text: b.heading_level
        for b in synthetic_blocks
        if b.block_type is BlockType.HEADING
    }
    assert levels["一、绪论"] < levels["1.1 背景"]


@requires(SYNTHETIC)
@pytest.mark.xfail(
    strict=True,
    reason="设计稿待办 5：_LINE_TOLERANCE 只看 y 不看 x，p3 的页眉(top≈80.4)与"
    "正文(top≈79.5)被按 y 聚成了同一行，两串文字逐字交错",
)
def test_synthetic_header_never_leaks_into_body(synthetic_blocks):
    """断言的是交错后的产物而非页眉原文：页眉被逐字拆进正文，
    `pdfplumber Draft` 变成了 `陷pdf阱plu、mb表er 格Dr独aft立`，
    原样的连续子串反而找不到。`Dr独aft` 就是这次交错的指纹。
    """
    assert not [b for b in synthetic_blocks if "Dr独aft" in b.text]


@requires(JOURNAL)
def test_journal_two_column_does_not_crash():
    """双栏本地路读出来是左右交错的乱序文本，属已知限制（交云端路）。
    这里只保证不炸、有产出——内容正确性不作断言，那是版面分析的活。"""
    assert PdfParser._parse_sync(JOURNAL.read_bytes())


@requires(SYNTHETIC)
async def test_public_parse_matches_sync(synthetic_blocks):
    """公开入口只是把同步实现丢进线程池（勿阻塞事件循环），结果必须一致。"""
    assert await PdfParser().parse(SYNTHETIC.read_bytes()) == synthetic_blocks
