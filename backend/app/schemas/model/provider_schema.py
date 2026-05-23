from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

ProviderType = Literal[
    "openai", "dashscope", "siliconflow", "deepseek", "anthropic", "custom"
]

ModelType = Literal[
    "chat", "embedding", "rerank", "vision", "tts", "stt", "image", "multimodal"
]


class ProviderCreate(BaseModel):
    """创建 Provider 请求体。"""

    name: str = Field(min_length=1, max_length=100, description="显示名")
    provider_type: ProviderType = Field(description="服务商类型")
    base_url: str = Field(min_length=1, max_length=512, description="API base URL")
    api_key: str = Field(min_length=1, description="API Key（明文，后端加密存储）")
    description: str = Field(default="", max_length=500, description="备注")


class ProviderUpdate(BaseModel):
    """更新 Provider 请求体，全部 Optional。"""

    name: str | None = Field(default=None, min_length=1, max_length=100)
    provider_type: ProviderType | None = None
    base_url: str | None = Field(default=None, min_length=1, max_length=512)
    api_key: str | None = Field(default=None, min_length=1, description="新 Key，留空不改")
    description: str | None = Field(default=None, max_length=500)


class ProviderOut(BaseModel):
    """Provider 对外输出（不含 api_key）。"""

    id: UUID
    name: str
    provider_type: str
    base_url: str
    description: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ProviderBrief(BaseModel):
    """内嵌在 ModelOut 中的 Provider 摘要。"""

    id: UUID
    name: str
    provider_type: str

    model_config = ConfigDict(from_attributes=True)
