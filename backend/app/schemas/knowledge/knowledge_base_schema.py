from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field
from app.models.knowledge import ParseBackend, RetrievalMode


class ChunkConfig(BaseModel):
    """库级切块配置（一套，作用于库内所有文档）。"""

    chunk_size: int = Field(default=512, ge=128, le=2048, description="子块大小（约 token 数）")
    overlap: int = Field(default=50, ge=0, le=512, description="相邻子块重叠")
    strategy: Literal["recursive"] = Field(default="recursive", description="切块策略")


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
    chunk_config: dict[str, Any]
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
