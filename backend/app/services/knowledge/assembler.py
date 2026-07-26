"""块 → 段的组装：按标题分组，并算出标题链。

站在 `parser`（认结构）与 `splitter`（段切子块）之间，管的是「哪些块
凑成一段」。三层分工：parser 说「这是二级标题」，assembler 说「这个标题
和它下面的正文是一段」，splitter 说「这段太长切成几块去 embed」。

**换解析后端不影响本层**——PDF 那条路同样产出 HEADING 块，组装规则共用。
"""

from dataclasses import dataclass

from app.services.knowledge.parser import BlockType, DocumentBlock

# 标题链的分隔符。给人看也给向量用，故取可读性好的形式而非路径式的 `/`
CHAIN_SEP = " > "

# 段长上限：**防极端的兜底**，不是常规切分手段。段本就该是完整的语义单元
# （一节讲完），两三千字的段是正常的——父段大正是父子块结构要的效果：子块小
# 保证匹配准，父段大保证上下文全。
# 这个值只挡住失控的情况：一节里塞进几万字的表格或代码块时，整段返回会撑爆
# prompt。实测本项目语料 p99 = 3657 字，故 4000 只切掉真正超标的那不到 1%。
# 不与 chunk_size 挂钩——它的依据是模型的上下文预算，不是子块多大。
MAX_PARAGRAPH_CHARS = 4000


@dataclass(frozen=True, slots=True)
class ParagraphDraft:
    """组装好但尚未落库的段。与 `DocumentBlock` 对称——一个是解析产物，
    一个是组装产物，都只在内存流转，落库仍是 `Paragraph` 表。

    `content` 含标题原文（命中后要交给模型，标题是有用的上下文）；
    `title` 是**带祖先的完整链**，这份信息 content 里没有——正文里只看得到
    直接的那级标题，看不到它属于哪一章。
    """

    content: str
    title: str


def _heading_text(text: str) -> str:
    """`## 3.1 向量检索` → `3.1 向量检索`。链里不留 `#`，它是噪音。"""
    return text.lstrip("#").strip()


def _push(stack: dict[int, str], block: DocumentBlock) -> None:
    """标题入栈：先清掉同级与更深的层级，再放自己。

    清同级是因为「3.1 → 3.2」时 3.1 已经过期；清更深是因为「3.1.1 → 3.2」
    时那一支整个结束了。不清就会拼出「3.1 > 3.1.1 > 3.2」这种鬼路径。
    """
    level = block.heading_level or 1
    for stale in [lv for lv in stack if lv >= level]:
        del stack[stale]
    stack[level] = _heading_text(block.text)


def assemble_paragraphs(
    blocks: list[DocumentBlock], max_chars: int = MAX_PARAGRAPH_CHARS
) -> list[ParagraphDraft]:
    """把块列表按标题分组成段，超长则在块边界续段。空输入返回 []。

    收尾时机三条：
    - **遇标题且当前段已有正文** → 收尾。「已有正文才收尾」是关键：`# 第三章`
      紧跟 `## 3.1`、中间没正文时，两个标题合进同一段开头，不会产生只有一行
      标题的段（那种段被 embed 后，命中只能返回孤零零一个标题）。
    - **正文不在任何标题底下** → 一个块一段。txt 全篇、md 第一个标题之前的
      前言都属此列：没有结构信号可依，攒到字数上限再切，切点落在哪只看凑够
      没有、与内容无关，与「段是完整语义单元」正相反。此时作者留下的唯一
      结构信号就是空行，故退化成按自然段切（即 v1 的行为）。
    - **再加下一块就超 `max_chars`** → 收尾，续段继承同一条标题链。

    没有第三条会失控：实测本项目语料若只按标题切，p99 段长 3657 字、最长
    6374 字，检索返回三段就把上下文塞满。
    """

    drafts: list[ParagraphDraft] = []
    stack: dict[int, str] = {}  # 标题层级 → 标题文字
    buf: list[str] = []  # 当前段攒的块文本
    buf_len = 0  # 当前段已攒字符数
    title = ""  # 当前段的标题链
    has_body = False  # 当前段是否已有正文

    def flush() -> None:
        """当前段定稿。读的是**调用时刻**的 `title` 变量，故收尾必须发生在
        `title` 重新赋值之前，否则第一段会被下一节的标题链污染。

        注意依赖的是赋值那行、不是 `_push`：栈更新完但 `title` 还没重算时，
        `flush()` 拿到的仍是旧值。变异测试实测确认（挪到 `_push` 之后全绿，
        挪到赋值之后 8 条测试变红）。
        """

        nonlocal buf, buf_len, has_body
        if buf:
            drafts.append(ParagraphDraft(content="\n\n".join(buf), title=title))
        buf, buf_len, has_body = [], 0, False

    for block in blocks:
        if block.block_type is not BlockType.HEADING:
            # 先判断再追加：切点因此落在两个块之间，不会把一个自然段劈开。
            # 单块自身就超限时不切——交给 splitter 去切子块，段该长就长。
            if has_body and (not title or buf_len + len(block.text) > max_chars):
                flush()
            buf.append(block.text)
            buf_len += len(block.text)
            has_body = True
            continue

        if has_body:
            flush()
        _push(stack, block)
        title = CHAIN_SEP.join(stack[lv] for lv in sorted(stack))
        buf.append(block.text)
        buf_len += len(block.text)

    flush()
    return drafts