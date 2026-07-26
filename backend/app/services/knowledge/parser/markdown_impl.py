"""Markdown 解析：认 ATX 标题，其余归正文。

与 `PlainTextParser` 的唯一差别是**给块打上类型和标题层级**，切段规则
一字不改（仍按空行）——第二步的契约是「只打标、不动边界」，这样标题
识别的效果才能被单独验证。真正改边界（标题并入正文、list-heavy 巨段）
是第三步的事。

**只认 ATX（`#`）不认 Setext（`===` / `---` 下划线）**：本项目 notes
的 YAML frontmatter 以 `---` 收尾，认 Setext 会把它判成二级标题；而
ATX 是绝对主流写法。

手写而不引 markdown 库，与 LlamaIndex（`MarkdownNodeParser`）、Dify
（`MarkdownExtractor`）一致——两家都是逐行扫 + 围栏布尔开关 + 一条正则。
分界线是「要不要真的渲染」：找结构边界手写就够，把 markdown 转成别的
格式（如 RAGFlow 用 Python-Markdown 把表格转 HTML）才该上库。
"""

import re

from app.services.knowledge.parser.base import BlockType, DocumentBlock, Parser
from app.services.knowledge.parser.decoding import decode_text

# CommonMark：最多 3 个前导空格；`#` 后须跟空白或行尾，故 `#tag` 不是标题
_HEADING = re.compile(r"^ {0,3}(#{1,6})(?:\s+.*)?$")
_FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})")


def _fence_flags(lines: list[str]) -> list[bool]:
    """逐行标记是否落在围栏代码块**内部**（围栏行本身记 False）。

    必须整篇扫一遍：代码块内部可以有空行，**先切段再逐段判断，围栏状态
    就断了**。实测本项目 43 份 md 里有 61 处代码块内的 `#`，不过滤就是
    11% 的假标题（`_format-spec.en.md` 在代码块里演示格式规范，里面的
    `# Title` `## TL;DR` 一个真标题都没有）。

    记住开启用的字符，避免 ``` 与 ~~~ 一开一闭错配。未闭合的围栏延续到
    文末，与 CommonMark 一致。
    """
    flags: list[bool] = []
    marker = ""  # 空 = 不在围栏内，否则为开启所用的字符
    for line in lines:
        matched = _FENCE.match(line)
        if not marker:
            flags.append(False)
            if matched:
                marker = matched.group(1)[0]
        elif matched and matched.group(1)[0] == marker:
            marker = ""
            flags.append(False)
        else:
            flags.append(True)
    return flags


def _to_blocks(para_lines: list[str], in_fence: bool) -> list[DocumentBlock]:
    """把一段的行组装成块。通常产出 1 个，标题与正文黏在一起时产出 2 个。

    **拆分是必要的而非顺手**：若让 HEADING 块的 text 里混着正文，这个标注
    本身就是错的，第三步据 `heading_level` 算标题链会把正文当成标题文字。
    打不准的标不如不打。实测本项目 2331 段里有 32 处（1.4%）走这条路，
    也是第二步唯一有意的边界变化。

    `text` 保留 markdown 原文（含 `#`）——IR 的 text 是展示形态，且纯标题
    文字随时可从中取，另存一份反而会与 text 不同步。
    """
    text = "\n".join(para_lines).strip()
    if not text:
        return []

    matched = None if in_fence else _HEADING.match(para_lines[0])
    if not matched:
        return [DocumentBlock(text=text, block_type=BlockType.PARAGRAPH)]

    heading = DocumentBlock(
        text=para_lines[0].strip(),
        block_type=BlockType.HEADING,
        heading_level=len(matched.group(1)),
    )
    rest = "\n".join(para_lines[1:]).strip()
    if not rest:
        return [heading]
    return [heading, DocumentBlock(text=rest, block_type=BlockType.PARAGRAPH)]


class MarkdownParser(Parser):
    """按空行切块（同 v1），块类型由首行判定。"""

    async def parse(self, raw: bytes) -> list[DocumentBlock]:
        lines = decode_text(raw).split("\n")
        in_fence = _fence_flags(lines)

        blocks: list[DocumentBlock] = []
        start = 0
        # 末尾补一个空行，让最后一段与其它段走同一条收尾路径
        for i, line in enumerate([*lines, ""]):
            # 判空用 `line` 而非 `line.strip()`：只有真正的空行才是段分隔，
            # 与 v1 的 `split("\n\n")` 对齐。代码块里的缩进空行（只含空格）
            # 长得像空行但不是，用 strip 判会把一个代码块劈成两半——实测
            # 本项目 3 份技术文档中招，且这种变化与标题识别毫无关系，会盖过
            # 真正该看的那 32 处。代码块内到底该不该切是第三步的议题。
            if line:
                continue
            if i > start:
                blocks.extend(_to_blocks(lines[start:i], in_fence[start]))
            start = i + 1
        return blocks
