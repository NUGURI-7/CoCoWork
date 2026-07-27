"""PDF 解析（本地轻量路）：pdfplumber 取字号 + 坐标，靠字号推标题层级。

**零配置可用**是这条路存在的理由——别人 clone 项目不配任何 key 就能跑 PDF。
结构靠猜，糙但够用；要真结构化走云端路（设计稿 D4）。

只处理**有文本层的单栏 PDF**。扫描件（无文本层）与双栏交由云端路，判定见
`parse()` 的返回值：块数为 0 即无文本层。双栏在本层只会读出左右交错的乱序文本
（实测记录见设计稿），属已知限制、不在此补救——那是版面分析的活。
"""

import asyncio
import logging
import re
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass
from io import BytesIO

import pdfplumber

from app.services.knowledge.parser.base import BlockType, DocumentBlock, Parser

logger = logging.getLogger(__name__)

# pdfminer 对每个缺 FontBBox 的字体刷一条 warning。Chrome 打印出的 PDF 能刷
# 几千行，把真正的日志淹掉；不影响解析结果，直接压掉。
logging.getLogger("pdfminer").setLevel(logging.ERROR)

# 同一行的 y 坐标容差（pt）。同行内字号不等时 top 会微差，
# 要求严格相等会把一行里的大小字拆成两行
_LINE_TOLERANCE = 2.0

# 字重只能从字体名猜——PDF 没有独立的 weight 字段
_BOLD_MARKERS = ("bold", "black", "heavy", "semibold")

# 页眉页脚的 top 量化桶（pt）。同一页眉在各页的 top 会有零点几的抖动
_TOP_BUCKET = 5.0

# 判为页眉页脚所需的最少出现页数。取 2 而非「过半」：期刊常奇偶页页眉不同
# （偶数页刊名 / 奇数页论文名），过半的门槛会让两者都漏掉
_RUNNING_MIN_PAGES = 2

# 「满行」的容差：行尾离右边界多远还算写满了。以字号为单位（1em = 一个字宽），
# 不写死 pt 值——换个字号不同的文档就失准
_FULL_LINE_SLACK_EM = 1.5

# 「首行缩进」的门槛：行首比正文左边界靠右多少算新段起头。中文排版惯例缩进 2 字，
# 取 1em 既抓得到又不会被 x0 的零点几抖动误判
_INDENT_MIN_EM = 1.0

# 目录页的点号引导线：`第一章 绪论 ...................... 1` 里那串点。
# **≥4 个而不是 ≥3**：英文省略号正好三个点（`wait...`），正文里满地都是；
# 实测目录引导线一行三十几个，门槛提到 4 一条都不会漏。
# 字符类收了半角点、全角点、间隔号、省略号——各家排版模板用哪个的都有。
_TOC_LEADER = re.compile(r"[.．·…]{4,}")

# 判定整页是目录所需的「引导线行」占比。实测学位论文的目录两页是 0.83 / 0.74，
# 三份 PDF 的其余所有页恒为 0，中间取 0.5，两边各留一倍余量
_TOC_LINE_RATIO = 0.5

# 判定目录页所需的最少行数。防的是只有两三行的稀疏页——那种页上一行命中
# 就够 50%，整页会被误毙
_TOC_MIN_LINES = 5

# 封面判定：该页最大字号至少是正文的多少倍。实测封面 42pt / 正文 12pt = 3.5 倍，
# 而学位论文里那些小字号的图注页只有 0.88 倍，1.5 把两类分得干干净净
_COVER_SIZE_RATIO = 1.5

# 封面判定的行数上限。这条挡的是**双栏期刊的首页**——实测那份论文第 3 页
# 大标题 19.7pt 是正文的 1.97 倍、且整页无正文字号行，前两个条件全中，
# 只有「51 行」这条拦得住它。封面不会有那么多行
_COVER_MAX_LINES = 20


@dataclass(frozen=True, slots=True)
class _Line:
    """一行文本 + 它的排版特征。

    **行是标题判定的最小单元**——判的是「这一行是不是标题」，不是「这个字符」。
    """

    text: str
    size: float  # 字号，取行内出现最多的那个
    bold: bool
    top: float  # 距页面顶端的距离
    x0: float  # 行首横坐标
    x1: float  # 行尾横坐标，判「满行」用
    page: int  # 页码，1 起


def _is_bold(fontname: str) -> bool:
    """从字体名猜字重。

    这个判断的可靠性直接决定启发式的上限：实测那份测试文档的一级标题只比正文
    大 1pt，纯字号阈值必漏，**能救回来全靠字重**。
    """
    lowered = fontname.lower()
    return any(marker in lowered for marker in _BOLD_MARKERS)


def _normalize(text: str) -> str:
    """只归一化**部首区**的字符，其余原样保留。

    不能整段 NFKC——它会把全角标点「，」「（」转成半角，那是改原文。中文正文里
    全角标点是标准写法，改了之后引用溯源对不上、检索也匹配不上。

    只动 U+2E80–U+2FDF 这一段（CJK 部首补充 + 康熙部首）：把 `⼀` 还原成 `一`。
    其中 CJK 部首补充段（如 `⻚`）没有兼容映射，NFKC 也修不了，原样留着——
    修不了总好过把别处改坏。
    """
    return "".join(
        unicodedata.normalize("NFKC", ch) if "\u2e80" <= ch <= "\u2fdf" else ch
        for ch in text
    )


def _group_lines(chars: list[dict], page_no: int) -> list[_Line]:
    """把一页的字符按 y 坐标聚成行。

    行内字号可能不一致（正文里嵌上标引用），故字号取**行内出现最多的**而非平均：
    实测论文有一行是 39 个 10pt 正文字 + 12 个 6pt 上标，取平均会算出一个
    文档里根本不存在的 9.x pt 档，后面的分档全歪。
    """
    buckets: dict[float, list[dict]] = defaultdict(list)
    for ch in chars:
        key = next(
            (k for k in buckets if abs(k - ch["top"]) <= _LINE_TOLERANCE),
            round(ch["top"], 1),
        )
        buckets[key].append(ch)

    lines: list[_Line] = []
    for top in sorted(buckets):
        group = sorted(buckets[top], key=lambda c: c["x0"])
        # NFKC：把兼容字符归一到标准写法（康熙部首 `⼀` → 汉字 `一` 等）。
        # 不做的话 `'⽂档' == '文档'` 为假、jieba 会把词切碎、检索永远匹配不上。
        # **只在 PDF 这条路做**：NFKC 会把全角空格转半角，而 markdown / txt 那边
        # 全角空格常是有意的首行缩进（见 decoding.py 的取舍）；PDF 的缩进靠坐标，
        # 不靠空格字符，故此处无此顾虑。
        text = _normalize("".join(c["text"] for c in group)).strip()
        if not text:
            continue
        sizes = Counter(round(c["size"], 1) for c in group)
        fonts = Counter(c["fontname"] for c in group)
        lines.append(
            _Line(
                text=text,
                size=sizes.most_common(1)[0][0],
                bold=_is_bold(fonts.most_common(1)[0][0]),
                top=round(top, 1),
                x0=round(min(c["x0"] for c in group), 1),
                x1=round(max(c["x1"] for c in group), 1),
                page=page_no,
            )
        )
    return lines


def _running_heads(lines: list[_Line]) -> set[tuple[float, str]]:
    """找出页眉页脚：**同一高度 + 同样文字，跨 2 页以上出现**。

    不靠字号也不靠位置区间，两者实测都不成立：
    - 靠字号不行——那份论文的页眉 13.1pt 比正文 10pt 还大，按「大就是标题」
      会每页伪造一个顶级标题，整条标题链稀碎；
    - 靠「页面顶部 15%」也不行——正文第一行同样落在那个区间里。

    「文字相同」是强条件：真标题不会重复出现在多页的同一高度。这条还顺手滤掉
    图表里的标签文字（实测抓到 `factory` / `grinding` / `90` 之类），那些本就该丢。
    """
    seen: dict[tuple[float, str], set[int]] = defaultdict(set)
    for ln in lines:
        seen[(round(ln.top / _TOP_BUCKET) * _TOP_BUCKET, ln.text)].add(ln.page)
    return {key for key, pages in seen.items() if len(pages) >= _RUNNING_MIN_PAGES}


def _is_toc_line(text: str) -> bool:
    """这一行是不是目录条目——靠点号引导线认，不靠内容。

    **刻意不要求「以页码结尾」**：实测那份学位论文的目录里，章级条目
    （14pt）与它的页码（12pt）字号不同，`top` 差了 2.6pt > `_LINE_TOLERANCE`，
    页码被甩成了单独一行，29 行里有 5 行如此。要求结尾带页码就会漏掉这批。
    """
    return _TOC_LEADER.search(text) is not None


def _cover_pages(lines: list[_Line], body_size: float) -> set[int]:
    """找出封面 / 扉页这类**没有正文的大字号页**。返回页码集合。

    封面上的字不是正文标题，是书名页：校名、论文题目、作者、日期。字号却是
    全文档最大的（实测 42pt / 24pt，正文才 12pt），按字号规则会被判成 H1 / H2；
    而封面之后再没有同级或更高的标题来把它们挤出栈（见 assembler 的 `_push`），
    于是**每一段的标题链前面都永远挂着这串垃圾**：`( ) > 研究 > 第三章 …`。

    三个条件缺一不可，每条都在实测里拦下了不同的东西：

    1. **该页没有任何一行是正文字号** —— 滤掉普通正文页；
    2. **该页最大字号 ≥ 正文的 1.5 倍** —— 滤掉小字号的图注 / 附表页
       （实测学位论文 p32 / p34 只有 0.88 倍，同样没有正文字号行）；
    3. **行数 ≤ 20** —— 滤掉**双栏期刊的首页**（实测 1.97 倍、无正文字号行，
       前两条全中，只有 51 行这条拦得住）。

    与目录页不同，封面**不整页丢弃**：论文题目只在这里出现一次，丢了就再也
    搜不到。处理方式是降级——内容照进库，只是不许当标题（见 `_build_blocks`）。
    """
    by_page: dict[int, list[_Line]] = defaultdict(list)
    for ln in lines:
        by_page[ln.page].append(ln)

    return {
        page
        for page, page_lines in by_page.items()
        if not any(ln.size == body_size for ln in page_lines)
           and max(ln.size for ln in page_lines) >= body_size * _COVER_SIZE_RATIO
           and len(page_lines) <= _COVER_MAX_LINES
    }


def _is_toc_page(lines: list[_Line]) -> bool:
    """整页是不是目录页。**是就整页丢弃**——目录是索引，不是内容。

    不丢的后果实测可见：目录行被切成段、进库、算向量、参与检索，用户搜
    「第一章 绪论」命中的是目录里那行 `第一章 绪论 ....... 1`，而不是正文。

    判定放在页级而非行级，是因为目录的特征本就是**成页出现**的：单看一行
    「含很多点」可能是正文里的分隔线，一整页大半行都这样只可能是目录。
    """
    if len(lines) < _TOC_MIN_LINES:
        return False
    hits = sum(1 for ln in lines if _is_toc_line(ln.text))
    return hits / len(lines) >= _TOC_LINE_RATIO


def _body_size(lines: list[_Line]) -> float:
    """定正文基准字号 = **行数最多的那个字号**（不分字重，正文里嵌的粗体强调
    不改变基准）。无输入时返回 0。

    **按行数不按字符数**——实测那份论文里 7.6pt 因为双栏交错导致每行长达 80 字，
    字符总量反超真正的正文（10pt、每行 33 字），基准一错，407 行正文全被判成
    标题。行数才反映「哪个字号在文档里出现得最普遍」，长行带不偏它。
    """
    line_count = Counter(ln.size for ln in lines)
    return line_count.most_common(1)[0][0] if line_count else 0.0


def _heading_levels(
        lines: list[_Line], body_size: float
) -> dict[tuple[float, bool], int]:
    """把标题候选的字号映射成层级，返回 `{(字号, 字重): 层级}`，层级 1 起。

    两条规则，都是实测定的：

    1. **标题 = 比正文大，或同字号但加粗**。后半条是必需的：测试文档的一级标题
       13pt 对正文 12pt 只大 1pt，MaxKB 那种「大 2pt 才算标题」的阈值会全漏。
    2. **层级按字号从大到小排**。前提是「字号越大层级越高」——排版约定如此
       （Word 默认样式 / LaTeX / 期刊模板皆然），MaxKB、RAGFlow 的实现同样建立
       在这个假设上。刻意造出的反例（H1 字号小于 H2）本层不处理。

    **调用前必须先剔掉表格区域的行、页眉页脚、封面页**：表头常是「同字号 +
    加粗」，封面则顶着全文档最大的字号，不剔都会被判成标题。
    """
    candidates = {
        (ln.size, ln.bold)
        for ln in lines
        if ln.size > body_size or (ln.size == body_size and ln.bold)
    }
    # 字号大的在前；同字号时加粗的算更高一档
    ordered = sorted(candidates, key=lambda sb: (-sb[0], not sb[1]))
    return {sb: level for level, sb in enumerate(ordered, 1)}


def _join_continuation(head: str, tail: str) -> str:
    """把续行接到上一行尾部。

    中文直接相接；两侧都是 ASCII 时补一个空格——PDF 在换行处**不存空格字符**，
    英文单词直接拼会粘成 `cementitiousmaterials`。中英交界处不补（一侧非 ASCII），
    因为中文与西文之间本就没有空格。
    """
    if head and tail and head[-1].isascii() and tail[0].isascii():
        return f"{head} {tail}"
    return head + tail


def _merge_paragraphs(lines: list[_Line], body_size: float) -> list[tuple[str, int]]:
    """把**连续的正文行**合并成段。返回 `[(段文本, 起始页码)]`。

    调用方负责在标题 / 表格处切断后再调本函数，故这里不必关心标题——标题必然是
    段边界，那个判断留在组装层。

    两个信号联合判断新段起头，缺一不可（实测依据）：

    - **上一行没写满** → 它是段末，本行开新段。主信号。
    - **本行有首行缩进** → 开新段。补上一条的漏：一段正好写满最后一行时，
      单看「满行」会把下一段错接上来。

    右边界按**页**算，取该页最靠右的行尾——不能用页面物理宽度，正文有页边距，
    永远碰不到纸边。跨页续行因此天然成立：不按页切断，上一页末行写满、下一页
    首行接着，自动合成一段。

    **为什么值得做**：本项目是父子块结构，段是「命中后整段交给 LLM」的交付单元，
    边界断了没有下游能补回来。Dify / MaxKB / LlamaIndex 都不做这件事，因为他们
    的块按固定长度硬切、段落边界本就不保留；RAGFlow 用 XGBoost 做过，因推理慢
    已自行关闭（`pdf_parser.py:1034` 裸 return）。

    已知失效：双栏（右边界变成栏边界，交给云端路）、居中的图注与公式行
    （天然短行，会被判成段末）。
    """
    if not lines:
        return []

    # 每页正文的右边界 = 该页最靠右的行尾
    right_edge: dict[int, float] = {}
    for ln in lines:
        right_edge[ln.page] = max(right_edge.get(ln.page, 0.0), ln.x1)

    # 正文左边界取 x0 的众数：绝大多数行顶格，缩进的首行是少数
    body_left = Counter(ln.x0 for ln in lines).most_common(1)[0][0]

    slack = body_size * _FULL_LINE_SLACK_EM
    indent_min = body_size * _INDENT_MIN_EM

    paragraphs: list[tuple[str, int]] = []
    buf = ""
    start_page = lines[0].page

    # zip 两两配对：prev 恒为 cur 的上一行，首轮 prev 是 None。
    # 不用 range + lines[i-1]——i=0 时那会绕到列表末尾，是个静默的坑
    for prev, cur in zip([None, *lines], lines):
        indented = cur.x0 > body_left + indent_min
        # prev 写到了它那一页的右边界附近 = 被排版截断 = cur 是它的续行
        continued = prev is not None and prev.x1 >= right_edge[prev.page] - slack

        if prev is None or indented or not continued:
            if buf:
                paragraphs.append((buf, start_page))
            buf, start_page = cur.text, cur.page
        else:
            buf = _join_continuation(buf, cur.text)

    if buf:
        paragraphs.append((buf, start_page))
    return paragraphs


def _table_to_markdown(table: list[list[str | None]]) -> str:
    """表格二维数组 → markdown 表格。首行当表头。

    转 markdown 而非保留制表符对齐：LLM 对 markdown 表格的理解明显更好，且它是
    纯文本、能直接进 embedding。表格独立成块不混进正文是设计稿的取舍——打散当
    普通文本切，检索「表里的数字」必然找不到（Dify 是直接把表丢掉的）。

    `extract_tables()` 的空单元格给 None，合并单元格会让各行列数不齐，
    故统一补齐到最宽那行。
    """
    rows = [
        [_normalize(cell or "").replace("\n", " ").replace("|", "\\|").strip() for cell in row]
        for row in table
        if row
    ]
    if not rows:
        return ""

    width = max(len(row) for row in rows)
    rows = [row + [""] * (width - len(row)) for row in rows]

    head, *body = rows
    out = ["| " + " | ".join(head) + " |", "|" + "---|" * width]
    out += ["| " + " | ".join(row) + " |" for row in body]
    return "\n".join(out)


def _in_any_box(char: dict, boxes: list[tuple[float, float, float, float]]) -> bool:
    """这个字符是否落在任一表格框内。box 是 pdfplumber 的 (左, 上, 右, 下)。"""
    x, y = char["x0"], char["top"]
    return any(x0 <= x <= x1 and top <= y <= bottom for x0, top, x1, bottom in boxes)


def _page_content(page, page_no: int) -> tuple[list[_Line], list[tuple[float, str]]]:
    """拆一页：返回 `(正文行, [(表格顶部坐标, markdown)])`。

    **表格区域的字符必须先剔掉**——它们同时存在于 `page.chars` 和
    `extract_tables()` 里，不剔就会出现两遍：一遍混进正文行，一遍是 markdown 表格。
    顺带也躲开了「表头常是同字号加粗」被误判成标题的坑。

    表格记下它的顶部坐标，是为了后面能按阅读顺序插回正文中间——表格在原文里
    夹在哪两段之间，组装时就得放回哪儿。

    整页无水平字符时返回 `([], [])`，由调用方并入「无可用文本」的页一并留痕。
    """
    # 整页都是旋转字符（竖排的评价表、盖章页）→ 整页放弃，表格也不要。
    # **必须单独拦这一道**，光过滤下面的 `page.chars` 不够：`extract_tables()`
    # 是自己重新读字符的，不受那道过滤影响——实测学位论文 p54 的竖排表照样被
    # 抽出来，单元格文字还是倒着的（`能力描述` 读成 `述描力能`），433 字垃圾进库。
    chars = page.chars
    if chars and not any(c.get("upright", True) for c in chars):
        return [], []

    tables = page.find_tables()
    boxes = [t.bbox for t in tables]

    # 零星的旋转字符（表格里的竖排表头、水印、侧栏批注）也丢：本地路按 y 坐标
    # 聚行，竖排文字会每字一行、顺序全乱。版面还原是云端路的活，认输比吐垃圾强。
    chars = [c for c in chars if c.get("upright", True) and not _in_any_box(c, boxes)]
    lines = _group_lines(chars, page_no)

    markdowns = [
        (t.bbox[1], md) for t in tables if (md := _table_to_markdown(t.extract()))
    ]
    return lines, markdowns


def _build_blocks(
        lines: list[_Line],
        tables: list[tuple[int, float, str]],
        running: set[tuple[float, str]],
        body_size: float,
        levels: dict[tuple[float, bool], int],
        cover_pages: set[int],
) -> list[DocumentBlock]:
    """
    把行与表格组装成块列表，这是解析流程的最后一环。
    行与表格**混在一起按 (页码, 高度) 排序**：表格在原文里夹在哪两段之间，
    组装时就得回到哪儿，否则读起来前言不搭后语。

    正文行不立即出块而是先攒着，直到撞上标题或表格才交给 `_merge_paragraphs`
    合并——**标题和表格天然就是段边界**，攒的这一批必定属于同一段落群。

    Args:
        lines: 全文档的正文行，表格区域的字已剔除。每行带文字 / 字号 / 字重 /
            坐标 / 页码。来自 `_page_content()` 逐页产出后的汇总。
        tables: 表格清单，元素是 `(页码, 表格顶部坐标, markdown 文本)`。
            带坐标是为了把表格插回它在原文里的位置。同样来自 `_page_content()`。
        running: 页眉页脚黑名单（running head 是「页眉」的排版术语），元素是
            `(量化后的高度, 行文字)`。当前行的这两项能在集合里查到 = 它是页眉
            页脚，直接丢。来自 `_running_heads()`。
        body_size: 正文字号，如 `12.0`。转交 `_merge_paragraphs()` 算满行与
            缩进的容差。来自 `_classify_sizes()`。
        levels: 字号对照表，`{(字号, 是否加粗): 标题层级}`，如 `{(16.0, True): 1}`。
            查得到 = 这行是标题、值即第几级；查不到 = 正文。来自 `_classify_sizes()`。
        cover_pages: 封面页页码集合，来自 `_cover_pages()`。这些页整页拼成
            一个正文块，不逐行走标题判定——否则封面上那几行全文档最大的字号
            会被判成 H1 / H2 且永不出栈，污染后面每一段的标题链。

    Returns:
        按阅读顺序排好的 `DocumentBlock` 列表，交给 assembler 分组成段。
    """
    blocks: list[DocumentBlock] = []
    buf: list[_Line] = []

    def flush() -> None:
        """把攒着的正文行合并成段，吐成块。"""
        for text, page in _merge_paragraphs(buf, body_size):
            blocks.append(
                DocumentBlock(text=text, block_type=BlockType.PARAGRAPH, page=page)
            )
        buf.clear()

    items: list[tuple[int, float, str, object]] = [
        (ln.page, ln.top, "line", ln) for ln in lines if ln.page not in cover_pages
    ]
    items += [(page, top, "table", md) for page, top, md in tables]
    # 封面整页拼成**一块**，不逐行进正文流程：封面是一个整体（校名 + 题目 +
    # 作者 + 日期），逐行走的话每行都被判成新段（行居中、x0 各不相同 →
    # `_merge_paragraphs` 的缩进信号全中），论文题目本身还会被折行切成两段，
    # 「保留内容」就白保留了。top 取 0 让它排在该页最前——整页本来就归它
    items += [
        (page, 0.0, "cover", "\n".join(ln.text for ln in lines if ln.page == page))
        for page in cover_pages
    ]
    items.sort(key=lambda item: (item[0], item[1]))

    for page, _top, kind, payload in items:
        if kind == "table":
            flush()
            blocks.append(
                DocumentBlock(text=str(payload), block_type=BlockType.TABLE, page=page)
            )
            continue

        if kind == "cover":
            flush()
            blocks.append(
                DocumentBlock(
                    text=str(payload), block_type=BlockType.PARAGRAPH, page=page
                )
            )
            continue

        line: _Line = payload  # type: ignore[assignment]
        # 页眉页脚：用与 _running_heads 一致的 key 反查，命中即丢
        if (round(line.top / _TOP_BUCKET) * _TOP_BUCKET, line.text) in running:
            continue

        level = levels.get((line.size, line.bold))
        if level is None:
            buf.append(line)  # 不是标题 → 正文，继续攒
            continue

        flush()
        blocks.append(
            DocumentBlock(
                text=line.text,
                block_type=BlockType.HEADING,
                heading_level=level,
                page=page,
            )
        )
    flush()
    return blocks


class PdfParser(Parser):
    """本地轻量路：pdfplumber 解析有文本层的单栏 PDF。

    流程：逐页取行与表格 → 找页眉页脚 → 定字号层级 → 组装成块。
    结构靠字号猜，糙但零配置可用；要真结构化走云端路。
    """

    async def parse(self, raw: bytes) -> list[DocumentBlock]:
        """解析 PDF 字节。空文件或无文本层时抛 `ValueError`。

        pdfplumber 是**同步阻塞**库，一份 20 页的 PDF 要跑几秒。直接在协程里调
        会把整个事件循环卡住（同进程的其他请求全部排队），故丢进线程池。
        """
        return await asyncio.to_thread(self._parse_sync, raw)

    @staticmethod
    def _parse_sync(raw: bytes) -> list[DocumentBlock]:
        """真正干活的同步实现，在线程池里跑。"""
        lines: list[_Line] = []
        tables: list[tuple[int, float, str]] = []
        empty_pages: list[int] = []  # 没有文本层的页
        toc_pages: list[int] = []  # 判定为目录、整页丢弃的页

        with pdfplumber.open(BytesIO(raw)) as pdf:
            total_pages = len(pdf.pages)
            for page_no, page in enumerate(pdf.pages, 1):
                page_lines, page_tables = _page_content(page, page_no)
                if not page_lines and not page_tables:
                    empty_pages.append(page_no)
                # 目录页在这里就拦掉，不能等到组装时再滤：晚一步的话目录的
                # 14pt 条目行已经进了字号统计，会在标题层级表里白占一档
                if _is_toc_page(page_lines):
                    toc_pages.append(page_no)
                    continue
                lines.extend(page_lines)
                tables.extend((page_no, top, md) for top, md in page_tables)

        if not lines and not tables:
            # 整份都没文本层 = 纯扫描件，本地路无能为力
            raise ValueError("该 PDF 没有文本层（疑似扫描件），需云端解析")

        # ↓ 新增：部分页没文本层（扫描的封面 / 盖章页 / 附录很常见）。
        # 不抛异常——其余页的内容是有效的，为几页缺失丢掉整份不划算；
        # 但必须留痕，否则就是「看着成功、实际少内容」的静默丢失。
        # 第 4 步接云端后，这里改成把这些页单独送去 OCR。
        if empty_pages:
            logger.warning(
                "PDF 有 %d/%d 页无可用文本，内容已丢失：第 %s 页",
                len(empty_pages),
                total_pages,
                ", ".join(map(str, empty_pages[:10])),
            )

        if toc_pages:
            logger.info(
                "PDF 丢弃 %d 页目录：第 %s 页",
                len(toc_pages),
                ", ".join(map(str, toc_pages)),
            )

        running = _running_heads(lines)
        # 定字号层级前**必须先剔页眉**：实测论文页眉 13.1pt 比正文 10pt 还大，
        # 不剔它会在层级表里白占一档，把真标题的层级整体挤偏。
        # 这里的 key 构造必须与 _running_heads / _build_blocks 三处一致。
        body_lines = [
            ln
            for ln in lines
            if (round(ln.top / _TOP_BUCKET) * _TOP_BUCKET, ln.text) not in running
        ]
        body_size = _body_size(body_lines)
        # 顺序不能换：认封面要先有正文字号，建层级表又要先把封面排掉。
        # 反过来算也不会错——封面页按定义就没有正文字号的行，剔掉它不可能
        # 改变「行数最多的字号」这个众数，故 body_size 不必重算
        cover_pages = _cover_pages(body_lines, body_size)
        levels = _heading_levels(
            [ln for ln in body_lines if ln.page not in cover_pages], body_size
        )

        if cover_pages:
            logger.info(
                "PDF 封面页降级为正文，不参与标题层级：第 %s 页",
                ", ".join(map(str, sorted(cover_pages))),
            )

        return _build_blocks(lines, tables, running, body_size, levels, cover_pages)
