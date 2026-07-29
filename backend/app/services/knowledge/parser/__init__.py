"""Parser 模块对外入口。

业务侧只 `from app.services.knowledge.parser import get_parser`，
按「文档类型 + 库级解析后端」取实现，不感知具体后端。
"""

from app.core.config import settings
from app.models.knowledge import ParseBackend
from app.services.knowledge.parser.baidu_impl import BaiduDocParser
from app.services.knowledge.parser.base import BlockType, DocumentBlock, Parser
from app.services.knowledge.parser.markdown_impl import MarkdownParser
from app.services.knowledge.parser.pdf_impl import PdfParser
from app.services.knowledge.parser.text_impl import PlainTextParser

# 装配硬编码（解析后端不是部署变量，不入 env），同 splitter 的模块级单例。
# 实现无状态，故每类型一个实例即可，不必按文档新建。
#
# key 是「格式 × 后端」两维：格式变多是加行，后端变多是加列，互不牵连。
# 云端那一列只登记它真有增量的格式 —— txt / md 走云端毫无意义：
# 多一次 HTTP、多烧一次额度，换回来的还是同一段纯文本。
_PARSERS: dict[tuple[str, ParseBackend], Parser] = {
    ("txt", ParseBackend.LOCAL): PlainTextParser(),
    ("md", ParseBackend.LOCAL): MarkdownParser(),
    ("pdf", ParseBackend.LOCAL): PdfParser(),
    ("pdf", ParseBackend.BAIDU): BaiduDocParser("pdf"),
}


def get_parser(file_type: str, backend: ParseBackend = ParseBackend.LOCAL) -> Parser:
    """按文档类型 + 解析后端取解析器。类型不支持时抛 `ValueError`。

    该后端没登记这个格式时**落回本地**而不是报错 —— 库选了 baidu，不代表
    库里每份文件都得走云端；一份 md 不该因为库级设置而处理失败。

    上传端已有扩展名白名单，走到这里还不支持 = 白名单与本表脱节，
    属编程错误，故用 `ValueError` 而非面向用户的 `ValidationException`。
    """
    parser = (
        _PARSERS.get((file_type, backend))
        or _PARSERS.get((file_type, ParseBackend.LOCAL))
    )
    if parser is None:
        raise ValueError(f"不支持的文档类型：{file_type}")
    return parser


def available_backends() -> list[ParseBackend]:
    """按部署侧配置返回可用的解析后端 —— 建库校验与前端选项共用一个真相。

    只看「配没配 Key」，**不去 ping 上游**：建库页面不该卡在别人家服务的
    响应时间上。连通性是配置时验一次的事，不是每次开页面都验一遍。
    """
    backends = [ParseBackend.LOCAL]  # 零配置底线，永远在列
    if settings.BAIDU_DOCPARSE_API_KEY and settings.BAIDU_DOCPARSE_SECRET_KEY:
        backends.append(ParseBackend.BAIDU)
    return backends


__all__ = [
    "BlockType",
    "DocumentBlock",
    "ParseBackend",
    "Parser",
    "available_backends",
    "get_parser",
]
