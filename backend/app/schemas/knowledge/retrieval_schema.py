"""命中测试（语义检索）相关 schema。

输入一句 query + top_k → 输出命中的段列表（含相似度分数）。
v1 纯向量检索：embed 子块搜得准、命中后返回整段（父子块），按段去重。
不落库（即时查询），是 RAG 检索的第一个消费方，不依赖 LLM / Agent。
"""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class RetrievalHit(BaseModel):
    """单条命中结果：命中子块所属的整段 + 来源 + 分数。

    - `content`：命中后返回给模型的**整段**（父子块的父级）。
    - `chunk_text`：实际命中的子块原文（`embedding.text`），调试切块时看。
    - `title`：段的标题链（`第三章 > 3.1 向量检索`）。与 `doc_name` 合起来
      构成完整出处；**祖先那几级是 `content` 里没有的信息**——正文只看得到
      直接的那级标题，看不到自己属于哪一章。
    - `page`：段的起始页（仅 PDF）。与 `title` 是同一类东西——定位信息，
      只是格式不同的文档能给出的形态不一样：PDF 给页码，md / txt 给标题链。
    - `score`：相似度 0~1，= 1 - 余弦距离，越大越相关。
    """

    paragraph_id: UUID = Field(description="命中段 id")
    document_id: UUID = Field(description="来源文档 id")
    doc_name: str = Field(description="来源文档名")
    title: str = Field(
        default="",
        description="段的标题链，如「第三章 > 3.1 向量检索」；无标题区域（txt / md 前言）为空串",
    )
    page: int | None = Field(
        default=None, description="段的起始页（仅 PDF；其余格式为 null）",
    )
    content: str = Field(description="命中段全文（返回给模型的单元）")
    chunk_text: str = Field(description="实际命中的子块原文")
    score: float = Field(description="相似度 0~1（vector=1-余弦距离；keyword=归一化 ts_rank；hybrid=RRF 共识分）")
    matched_by: Literal["vector", "keyword", "both"] | None = Field(
        default=None, description="hybrid 模式命中来源路；单模式检索为 None",
    )

class RetrievalTestOut(BaseModel):
    """命中测试响应：命中列表 + 耗时（不落库，仅本次响应展示）。

    耗时拆四段，定位是 embedding 慢、SQL 慢还是精排慢：
    - embed_ms：query 向量化耗时（调 embedding 模型，网络请求，通常占大头）
    - search_ms：pgvector 检索 SQL 耗时（本地 DB，通常很快）
    - rerank_ms：精排打分耗时（调 rerank 模型，网络请求；未开启为 0）
    - total_ms：service 内总耗时
    """

    hits: list[RetrievalHit] = Field(description="命中段列表")
    embed_ms: float = Field(description="query 向量化耗时（毫秒）")
    search_ms: float = Field(description="检索 SQL 耗时（毫秒）")
    rerank_ms: float = Field(default=0.0, description="精排耗时（毫秒），未开启 rerank 时为 0")
    total_ms: float = Field(description="总耗时（毫秒）")



