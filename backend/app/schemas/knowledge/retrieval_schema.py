"""命中测试（语义检索）相关 schema。

输入一句 query + top_k → 输出命中的段列表（含相似度分数）。
v1 纯向量检索：embed 子块搜得准、命中后返回整段（父子块），按段去重。
不落库（即时查询），是 RAG 检索的第一个消费方，不依赖 LLM / Agent。
"""

from uuid import UUID

from pydantic import BaseModel, Field


class RetrievalHit(BaseModel):
    """单条命中结果：命中子块所属的整段 + 来源 + 分数。

    - `content`：命中后返回给模型的**整段**（父子块的父级）。
    - `chunk_text`：实际命中的子块原文（`embedding.text`），调试切块时看。
    - `score`：相似度 0~1，= 1 - 余弦距离，越大越相关。
    """

    paragraph_id: UUID = Field(description="命中段 id")
    document_id: UUID = Field(description="来源文档 id")
    doc_name: str = Field(description="来源文档名")
    content: str = Field(description="命中段全文（返回给模型的单元）")
    chunk_text: str = Field(description="实际命中的子块原文")
    score: float = Field(description="相似度 0~1（1 - 余弦距离）")

class RetrievalTestOut(BaseModel):
    """命中测试响应：命中列表 + 耗时（不落库，仅本次响应展示）。

    耗时拆三段，定位是 embedding 慢还是 SQL 慢：
    - embed_ms：query 向量化耗时（调 embedding 模型，网络请求，通常占大头）
    - search_ms：pgvector 检索 SQL 耗时（本地 DB，通常很快）
    - total_ms：service 内总耗时
    """

    hits: list[RetrievalHit] = Field(description="命中段列表")
    embed_ms: float = Field(description="query 向量化耗时（毫秒）")
    search_ms: float = Field(description="检索 SQL 耗时（毫秒）")
    total_ms: float = Field(description="总耗时（毫秒）")


