"""命中测试（语义检索）相关 schema。

输入一句 query + top_k → 输出命中的段列表（含相似度分数）。
v1 纯向量检索：embed 子块搜得准、命中后返回整段（父子块），按段去重。
不落库（即时查询），是 RAG 检索的第一个消费方，不依赖 LLM / Agent。
"""

from uuid import UUID

from pydantic import BaseModel, Field

class RetrievalTestIn(BaseModel):
    """命中测试请求体。top_k / similarity_threshold 是查询时旋钮，不进表。"""
    query: str = Field(min_length=1, max_length=2000, description="查询文本")
    top_k: int = Field(default=5, ge=1, le=50, description="返回命中段数")
    similarity_threshold: float = Field(
        default=0.0, ge=0.0, le=1.0,
        description="相似度阈值，低于此分的命中不返回；默认 0 = 不过滤",
    )

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




