"""Parser 抽象层：把文件字节解析成结构化块列表（IR）。

存在的理由是**结构信息不能在到达切块器之前被抹平**——纯文本抽取会把
「这行是二级标题」这个事实丢掉，下游只能按分隔符硬切。IR 让解析器把
类型 / 标题层级 / 页码显式写成字段，切块器据此做语义边界切分。

设计见 `docs/design/pdf-parsing-v1.md`。业务侧（process_document）只依赖
本 ABC 的 parse 方法，换解析后端不动业务代码。
"""

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

# 正文里图的占位记号 [[figure:N]]：解析器在图的原位留下它，渲染方据此把图摆回去。
# **格式的唯一真相在这里**——生产走 figure_marker、抠除走 strip_figure_markers，
# 两头都引用本模块，别处不许手写这个字面量，免得哪天改格式了另一头正则悄悄失配。
_FIGURE_MARKER_RE = re.compile(r"\[\[figure:\d+\]\]")


def figure_marker(index: int) -> str:
    """生产正文里的图占位记号。index 与 FIGURE 块 meta 的 index 同值。"""
    return f"[[figure:{index}]]"


def strip_figure_markers(text: str) -> str:
    """抠掉记号并收拢它留下的空行。

    喂向量 / 建关键词索引前用——记号是给渲染看的路标，混进检索文本是噪音。
    **存进 Paragraph.content 的正文不过这道**：那份要留记号才摆得回图。
    """
    cleaned = _FIGURE_MARKER_RE.sub("", text)
    return re.sub(r"\n{3,}", "\n\n", cleaned).strip()


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
    # 类型专属元数据。FIGURE 块的 meta 是解析器与处理管线之间的合同，分两阶段：
    #   解析器产出时：{"image_bytes": bytes, "index": int, "bbox": (x0, top, x1, bottom)}
    #     —— image_bytes 是裁出来的 PNG 字节，index 是文档内自增编号（与正文记号
    #        [[figure:N]] 的 N 同值），bbox 是图在页面上的框。
    #   管线存图后：image_bytes 换成 "figure_key"（对象存储 key），字节不再驻留内存。
    # 其余块类型暂不使用 meta（HEADING 的层级 / PARAGRAPH 的页码各有专属字段）。
    meta: dict[str, Any] = field(default_factory=dict)


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