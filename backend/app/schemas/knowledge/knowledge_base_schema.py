from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from app.models.knowledge import ParseBackend, RetrievalMode


class ChunkConfig(BaseModel):
    """库级切块配置（一套，作用于库内所有文档）。

    `chunk_size` / `overlap` 的单位是 **token**（cl100k_base 口径，见
    `splitter.sentence_impl`）——不是字符。中文一字约 1.1~1.2 token，
    故 256 折合 210~230 个汉字。

    **默认值曾下调到 128，实测判退**（2026-08-15，医疗基准 1000 题）：
    recall@10 0.799 → 0.769、mrr@10 0.678 → 0.649。原因是该语料段落中位数
    仅 160 token 上下，本身就是完整的检索单元，切碎反而劈开语义。
    256 是与改造前（256 字符）大致等长的档位，只是口径统一到了 token。
    """

    chunk_size: int = Field(default=256, ge=64, le=2048, description="子块大小（token）")
    overlap: int = Field(
        default=20, ge=0, le=512,
        description="相邻子块重叠（token）；实际向上取整到完整句子，且不超过半块",
    )
    prepend_title: bool = Field(
        default=True,
        description="算向量前是否给子块前置段的标题链；只影响送去 embedding 的文本，不影响落库的子块原文",
    )


class KnowledgeBaseCreate(BaseModel):
    """创建知识库请求体。embedding_dim 由后端随模型锁定，不在此处传。"""

    name: str = Field(min_length=1, max_length=150, description="库名")
    description: str = Field(default="", max_length=500, description="描述")
    embedding_model_id: UUID = Field(description="锁定的 embedding 模型（type=embedding）")
    chunk_config: ChunkConfig = Field(default_factory=ChunkConfig, description="切块配置")
    parse_backend: ParseBackend = Field(
        default=ParseBackend.LOCAL,
        description="文档解析后端；哪些可选随部署配置而定，见 GET /knowledge-bases/parse-backends",
    )


class KnowledgeBaseUpdate(BaseModel):
    """更新知识库请求体。不可改 embedding 模型（换模型 = 全库重建）。"""

    name: str | None = Field(default=None, min_length=1, max_length=150)
    description: str | None = Field(default=None, max_length=500)
    chunk_config: ChunkConfig | None = None
    retrieval_mode: RetrievalMode | None = None
    rerank_model_id: UUID | None = None
    parse_backend: ParseBackend | None = Field(
        default=None, description="改了只影响此后新传的文档，存量文档需重跑才生效",
    )


class KnowledgeBaseOut(BaseModel):
    """知识库对外输出。"""

    id: UUID
    name: str
    description: str
    embedding_model_id: UUID
    embedding_model_name: str
    embedding_dim: int
    # 用 ChunkConfig 而非裸 dict：出参过一遍 Pydantic，jsonb 里缺的键（存量库
    # 建库时还没有的新配置项）自动补默认值。否则前端拿到 undefined，会把
    # 「后端默认开着」显示成「未开启」——显示与实际行为相反
    chunk_config: ChunkConfig
    status: str
    doc_count: int = 0
    chunk_count: int = 0
    retrieval_mode: str
    rerank_model_id: UUID | None = None
    rerank_model_name: str | None = None
    parse_backend: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
