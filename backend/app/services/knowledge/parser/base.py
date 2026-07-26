"""Parser 抽象层：把文件字节解析成结构化块列表（IR）。

存在的理由是**结构信息不能在到达切块器之前被抹平**——纯文本抽取会把
「这行是二级标题」这个事实丢掉，下游只能按分隔符硬切。IR 让解析器把
类型 / 标题层级 / 页码显式写成字段，切块器据此做语义边界切分。

设计见 `docs/design/pdf-parsing-v1.md`。业务侧（process_document）只依赖
本 ABC 的 parse 方法，换解析后端不动业务代码。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class BlockType(StrEnum):
    """块类型。不落库（IR 只在内存流转），故住在使用处而非 models。"""

    HEADING = "heading"
    PARAGRAPH = "paragraph"
    TABLE = "table"
    FIGURE = "figure"


@dataclass(frozen=True, slots=True)
class DocumentBlock:
    """解析产物的最小单元：一块内容 + 它的结构身份。

    只在内存中流转（解析器造 → 分段器消费），不落库——落库仍是
    Paragraph / Embedding 两张表。同 `AgentSpec` / `RetrievalResult`。

    `text` 是展示形态（表格为 markdown、图为占位符）；被 embed 的文本
    由下游决定——`Paragraph.content` 与 `Embedding.text` 本就是分离的，
    IR 层不重复这层分离。
    """

    text: str
    block_type: BlockType
    heading_level: int | None = None  # 标题层级，1 起；仅 HEADING 有值
    page: int | None = None  # 页码，1 起；仅 PDF 类解析器有值（P4 引用溯源的上游）
    meta: dict[str, Any] = field(default_factory=dict)  # 类型专属：figure 的 key / alt 等


class Parser(ABC):
    """文档解析器接口：文件字节 → 结构化块列表。"""

    @abstractmethod
    async def parse(self, raw: bytes) -> list[DocumentBlock]:
        """解析文件字节。空文件返回 []。

                `async` 是为托管解析 API 留的（第四步走 HTTP）；纯 CPU 实现直接
                `async def` 不 await 即可，阻塞型库（pdfplumber）自行
                `asyncio.to_thread` 包一层，勿阻塞事件循环。

                约定 parse-don't-validate：认不出的内容降级为 PARAGRAPH 或跳过，
                不抛异常——单个畸形块不该让整份文档处理失败。
                """
        ...