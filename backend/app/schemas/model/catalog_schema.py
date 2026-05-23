from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.model.provider_schema import ModelType, ProviderType


class CatalogCreate(BaseModel):
    """管理员创建目录条目。"""

    provider_type: ProviderType
    model_id: str = Field(min_length=1, max_length=100, description="上游模型标识")
    model_type: ModelType


class CatalogOut(BaseModel):
    """目录条目输出。"""

    id: UUID
    provider_type: str
    model_id: str
    model_type: str

    model_config = ConfigDict(from_attributes=True)
