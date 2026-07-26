"""纯文本解析：解码 → 按空行切块。

txt 本就无结构可言，块一律归 PARAGRAPH。markdown 第一步曾走这里，第二步
起改道 `MarkdownParser`（认 `#` 打标题层级）。

切块逻辑逐字复刻 v1 的 `_split_paragraphs`（按 `\\n\\n` 切、strip、丢空段）。
解码与规范化是本片唯一有意偏离 v1 的地方，理由见 `decoding.decode_text`；
契约的准确表述是「**已经正确的用例结果不变**」，而非连既有 bug 一起保留。
"""

from app.services.knowledge.parser.base import BlockType, DocumentBlock, Parser
from app.services.knowledge.parser.decoding import decode_text


class PlainTextParser(Parser):
    """按空行切块，全部记为 PARAGRAPH。无标题层级、无页码。"""

    async def parse(self, raw: bytes) -> list[DocumentBlock]:
        text = decode_text(raw)
        return [
            DocumentBlock(text=stripped, block_type=BlockType.PARAGRAPH)
            for para in text.split("\n\n")
            if (stripped := para.strip())
        ]
