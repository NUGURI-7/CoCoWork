"""assemble_paragraphs 单测 —— 纯内存、零 DB 零 API。

这一层为什么值得单测：它**带状态**。`stack` / `buf` / `has_body` 都跨循环
轮次累积，这类代码的 bug 特征是「前两个输入都对、第三个才崩」，读代码
读不出来。而且它错了**不报错**——标题链拼脏了，整条流水线照样跑到
completed，只有翻数据库才看得见。

三类断言，性质不同：

1. **标题栈的出入栈**（`_push` 那几行）——真正可能写错的地方。
2. **段边界**（何时收尾、何时续段）——决定检索的粒度。其中「无标题区域
   退化成按块切」这条尤其要在**有标题**的语境下另测一遍超长逻辑，否则
   无标题那条路径会先触发、把超长逻辑整个盖住（测试照样绿，测的却是
   另一回事）。
3. **回归界碑**：`content` 是原文忠实切片、续段不重复标题行、`title` 存
   完整链。这几条是绕了好几轮才定的决策，测试在这里不是为了找 bug，
   是为了防止日后有人重构时顺手改掉。

`max_chars` 用小值（10 上下）而非默认 4000：造四千字样本只会让用例读不懂，
而该函数把上限做成参数本就是为了可调——顺带也可测。
"""

import pytest

from app.services.knowledge.assembler import (
    CHAIN_SEP,
    MAX_PARAGRAPH_CHARS,
    assemble_paragraphs,
)
from app.services.knowledge.parser import BlockType, DocumentBlock


def h(text: str, level: int) -> DocumentBlock:
    """造标题块。`text` 写 markdown 原文（含 `#`），与 parser 的产出一致。"""
    return DocumentBlock(text=text, block_type=BlockType.HEADING, heading_level=level)


def p(text: str) -> DocumentBlock:
    """造正文块。"""
    return DocumentBlock(text=text, block_type=BlockType.PARAGRAPH)


# --- 退化输入 ---


def test_empty_input_returns_empty():
    """空文档不该产出空段——落一条 content='' 的 Paragraph 进库更难查。"""
    assert assemble_paragraphs([]) == []


def test_heading_without_level_defaults_to_one():
    """`heading_level=None` 当作 1 级，不炸。

    parse-don't-validate：解析器认出「这是标题」但拿不准层级（PDF 那条路
    靠字号猜，本就可能猜不出）时，段仍要正常产出。
    """
    headless = DocumentBlock(text="T", block_type=BlockType.HEADING)  # heading_level=None
    assert assemble_paragraphs([headless, p("A")])[0].title == "T"


# --- 标题链：出入栈 ---


@pytest.mark.parametrize(
    ("headings", "expected_titles"),
    [
        # 同级推进：后一个顶掉前一个，不叠加
        ([("A", 1), ("B", 1)], ["A", "B"]),
        # 逐级深入：链一路加长
        ([("A", 1), ("B", 2)], ["A", "A > B"]),
        ([("A", 1), ("B", 2), ("C", 3)], ["A", "A > B", "A > B > C"]),
        # 深层跳回浅层：中间层连同更深层一起出栈，不留 "A > B > C > D" 残渣
        ([("A", 1), ("B", 2), ("C", 3), ("D", 2)], ["A", "A > B", "A > B > C", "A > D"]),
        # 跳回顶层：整条链清空重来
        ([("A", 1), ("B", 2), ("C", 3), ("D", 1)], ["A", "A > B", "A > B > C", "D"]),
        # 层级跳跃（H1 直接到 H3）：缺的那级不占位，也不补空
        ([("A", 1), ("B", 3)], ["A", "A > B"]),
    ],
)
def test_title_chain(headings: list[tuple[str, int]], expected_titles: list[str]):
    """标题链随层级升降正确增删。

    每个标题后都跟一段正文，故每个标题各开一段，段数 = 标题数。
    这几组覆盖 `_push` 里「清同级」与「清更深」两条规则的所有组合——
    不清就会拼出 `3.1 > 3.1.1 > 3.2` 这种既不存在也无法溯源的路径。
    """
    blocks: list[DocumentBlock] = []
    for text, level in headings:
        blocks.extend([h(f"{'#' * level} {text}", level), p(f"{text} 的正文")])
    assert [d.title for d in assemble_paragraphs(blocks)] == expected_titles


def test_title_strips_hash_prefix():
    """链里不留 `#`——它是 markdown 的语法噪音，且 PDF 那条路根本没有。"""
    drafts = assemble_paragraphs([h("## 3.1 向量检索", 2), p("正文")])
    assert drafts[0].title == "3.1 向量检索"


def test_title_uses_declared_separator():
    """分隔符取自模块常量，测试不重复硬编码 `' > '`。"""
    drafts = assemble_paragraphs([h("# 一", 1), h("## 二", 2), p("正文")])
    assert drafts[0].title == f"一{CHAIN_SEP}二"


def test_first_paragraph_not_polluted_by_next_heading():
    """收尾必须发生在标题栈更新**之前**，否则第一段会挂上下一节的链。

    这是本函数最隐蔽的顺序依赖：`flush()` 读的是调用时刻的 `title`。
    两行代码调个位就错，且错得很安静——每段都有 title，只是全错一位。
    """
    drafts = assemble_paragraphs([h("## 3.1", 2), p("A"), h("## 3.2", 2), p("B")])
    assert [d.title for d in drafts] == ["3.1", "3.2"]


# --- 段边界：何时收尾 ---


def test_consecutive_headings_merge_into_one_paragraph():
    """`# 第三章` 紧跟 `## 3.1`、中间无正文时合进同一段。

    否则会产出一个只有标题、没有正文的段。那种段被 embed 之后，命中它
    等于返回给模型一行孤零零的标题——占着 top_k 名额却不含任何信息。
    """
    drafts = assemble_paragraphs([h("# 第三章", 1), h("## 3.1", 2), p("正文")])
    assert len(drafts) == 1
    assert drafts[0].title == "第三章 > 3.1"


def test_heading_after_body_starts_new_paragraph():
    """正文之后遇标题即收尾——标题是语义边界，这是标题感知切块的本体。"""
    assert len(assemble_paragraphs([h("# A", 1), p("正文"), h("# B", 1), p("正文")])) == 2


def test_blocks_under_same_heading_join_with_blank_line():
    """同一标题下的多个块攒成一段，用空行连接还原成原文的样子。

    这正是父子块结构要的效果——子块小保匹配准，父段完整保上下文全。
    """
    drafts = assemble_paragraphs([h("# T", 1), p("第一块"), p("第二块")])
    assert len(drafts) == 1
    assert drafts[0].content == "# T\n\n第一块\n\n第二块"


# --- 无标题区域：退化成按块切 ---


def test_document_without_headings_splits_per_block():
    """无标题的文档（txt 全篇）按自然段切，一个块一段。

    段的定义是「一个完整语义单元」，边界由标题给出。没有标题就没有边界
    可依——此时若攒到 `max_chars` 再切，切点落在哪只取决于字数凑够没有、
    与内容无关，与这个定义正相反。作者留下的唯一结构信号是空行，故退化
    成按自然段切（即 v1 的行为）。
    """
    drafts = assemble_paragraphs([p("A"), p("B"), p("C")])
    assert [d.content for d in drafts] == ["A", "B", "C"]
    assert all(d.title == "" for d in drafts)


def test_preamble_before_first_heading_splits_per_block():
    """md 里第一个标题之前的前言，同样按块切。

    判据是「当前有没有标题罩着」（`title` 是否为空），而非「整份文档有没有
    标题」——后者要预扫描一遍，还处理不了前言这种同一文档内的混合情形。
    """
    blocks = [p("前言一"), p("前言二"), h("# 正文", 1), p("正文段")]
    assert [(d.title, d.content) for d in assemble_paragraphs(blocks)] == [
        ("", "前言一"),
        ("", "前言二"),
        ("正文", "# 正文\n\n正文段"),
    ]


# --- 续段：max_chars 兜底 ---


def test_oversized_paragraph_splits_between_blocks():
    """超限时切点落在两个块之间，不把一个自然段劈成两半。

    **必须在标题底下测**：无标题时本就一块一段，那条路径会先触发、把超长
    逻辑整个盖住——测试照样绿，测的却是另一回事。
    """
    drafts = assemble_paragraphs(
        [h("# T", 1), p("a" * 6), p("b" * 6), p("c" * 6)], max_chars=12
    )
    assert [d.content for d in drafts] == ["# T\n\n" + "a" * 6, "b" * 6 + "\n\n" + "c" * 6]


def test_continuation_inherits_title_chain():
    """续段继承同一条标题链——它们本就是同一节的内容。"""
    drafts = assemble_paragraphs([h("# T", 1), p("a" * 8), p("b" * 8)], max_chars=10)
    assert [d.title for d in drafts] == ["T", "T"]


def test_continuation_does_not_repeat_heading_line():
    """续段的 content **不重复标题行**。

    `content` 是原文的忠实切片，凭空插一行原文里没有的标题，引用溯源
    （roadmap P4）就对不上位置了。标题信息走 `title` 字段，不进正文。
    """
    drafts = assemble_paragraphs([h("# T", 1), p("a" * 8), p("b" * 8)], max_chars=10)
    assert drafts[0].content == "# T\n\n" + "a" * 8
    assert drafts[1].content == "b" * 8


def test_single_oversized_block_is_not_split():
    """单个块自身就超限时**不切**——段该长就长，交给 splitter 去切子块。

    在这里切等于凭字数硬劈一个自然段（或一张表、一个代码块），破坏的
    正是父子块结构要保的东西：子块小保匹配准，父段完整保上下文全。
    """
    drafts = assemble_paragraphs([p("x" * 50)], max_chars=10)
    assert len(drafts) == 1
    assert len(drafts[0].content) == 50


def test_default_max_chars_is_generous():
    """默认上限是防极端的兜底，不是常规切分手段。

    钉住量级而非具体数值：实测本项目语料 p99 段长 3657 字，上限落在
    数千这一档才只切掉真正失控的那不到 1%。调到几百就变成了按字数硬切，
    与「段是完整语义单元」的设计直接冲突。
    """
    assert MAX_PARAGRAPH_CHARS >= 2000


# --- content 忠实性 ---


def test_content_keeps_heading_markup():
    """`content` 保留标题原文（含 `#`）——它是原文切片，不是加工产物。

    命中后交给模型的就是这段，标题本身是有用的上下文；而 `title` 存的是
    **带祖先的完整链**，那份信息 content 里没有（正文只看得到直接的那级
    标题，看不到自己属于哪一章）。两者不重复、各有各的用处。
    """
    drafts = assemble_paragraphs([h("## 3.1 向量检索", 2), p("正文")])
    assert drafts[0].content == "## 3.1 向量检索\n\n正文"
