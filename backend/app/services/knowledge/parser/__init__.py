"""Parser 模块对外入口。

业务侧只 `from app.services.knowledge.parser import get_parser`，
按文档类型取实现、不感知具体后端。新增格式 = 在 `_PARSERS` 加一行。
"""

from app.services.knowledge.parser.base import BlockType, DocumentBlock, Parser
from app.services.knowledge.parser.markdown_impl import MarkdownParser
from app.services.knowledge.parser.text_impl import PlainTextParser

# 装配硬编码（解析后端不是部署变量，不入 env），同 splitter 的模块级单例。
# 实现无状态，故每类型一个实例即可，不必按文档新建。
_PARSERS: dict[str, Parser] = {
    "txt": PlainTextParser(),
    "md": MarkdownParser(),
}


def get_parser(file_type: str) -> Parser:
    """按文档类型取解析器。类型不支持时抛 `ValueError`。

    上传端已有扩展名白名单，走到这里还不支持 = 白名单与本表脱节，
    属编程错误，故用 `ValueError` 而非面向用户的 `ValidationException`。
    """
    parser = _PARSERS.get(file_type)
    if parser is None:
        raise ValueError(f"不支持的文档类型：{file_type}")
    return parser


__all__ = ["BlockType", "DocumentBlock", "Parser", "get_parser"]