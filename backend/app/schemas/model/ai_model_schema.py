from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.model.provider_schema import ModelType


class ModelCreate(BaseModel):
    """创建 AIModel 请求体。

    `provider_id` 不在 body —— 由 URL path 提供（POST /providers/{pid}/models），
    避免 path 和 body 双源歧义。
    """

    model_name: str = Field(min_length=1, max_length=100, description="上游模型 ID")
    display_name: str = Field(min_length=1, max_length=100, description="展示名")
    model_type: ModelType = Field(description="chat / embedding / rerank")
    config: dict[str, Any] = Field(default_factory=dict, description="参数预设")
    base_url: str | None = Field(default=None, max_length=512, description="覆盖 Provider 的 base URL")
    api_key: str | None = Field(default=None, description="覆盖 Provider 的 API Key")
    is_enabled: bool = Field(default=True)


class ModelUpdate(BaseModel):
    """更新 AIModel 请求体，全部 Optional。不可改 provider_id。"""

    model_name: str | None = Field(default=None, min_length=1, max_length=100)
    display_name: str | None = Field(default=None, min_length=1, max_length=100)
    model_type: ModelType | None = None
    config: dict[str, Any] | None = None
    base_url: str | None = Field(default=None, max_length=512)
    api_key: str | None = Field(default=None, description="新 Key，留空不改")
    is_enabled: bool | None = None


class ModelOut(BaseModel):
    """AIModel 对外输出，内嵌 Provider 摘要。"""

    id: UUID
    model_name: str
    display_name: str
    model_type: str
    config: dict[str, Any]
    meta: dict[str, Any] | None = Field(
        default=None, description="模型固有事实：embedding 维度等（非用户可调）"
    )
    has_custom_base_url: bool = Field(
        default=False, description="是否覆盖了 Provider 的 base_url"
    )
    has_custom_api_key: bool = Field(
        default=False, description="是否覆盖了 Provider 的 api_key"
    )
    is_enabled: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


# ==================== 参数定义（动态表单元数据）====================


class ParamField(BaseModel):
    """单个参数的字段定义，前端据此渲染控件。"""

    key: str
    label: str
    type: Literal["number", "slider", "switch"]
    min: float | None = None
    max: float | None = None
    step: float | None = None
    default: float | bool | None = None
    description: str | None = None


class ModelTypeParams(BaseModel):
    """某个 model_type 的参数定义集。"""

    config_fields: list[ParamField] = Field(description="模型能力（只读参考）")
    invocation_params: list[ParamField] = Field(description="调用参数（可配预设）")


# 静态参数定义常量 —— 前端通过 GET /models/param-definitions 获取
PARAM_DEFINITIONS: dict[str, ModelTypeParams] = {
    "chat": ModelTypeParams(
        config_fields=[
            ParamField(key="context_window", label="上下文窗口", type="number", default=128000),
            ParamField(key="max_output_tokens", label="最大输出 Token", type="number", default=8192),
        ],
        invocation_params=[
            ParamField(key="temperature", label="Temperature", type="slider", min=0, max=2, step=0.1, default=1.0),
            ParamField(key="top_p", label="Top P", type="slider", min=0, max=1, step=0.01, default=1.0),
            ParamField(key="max_tokens", label="Max Tokens", type="number", min=1, default=None, description="留空则使用模型默认值"),
            ParamField(key="frequency_penalty", label="Frequency Penalty", type="slider", min=-2, max=2, step=0.1, default=0),
            ParamField(key="presence_penalty", label="Presence Penalty", type="slider", min=-2, max=2, step=0.1, default=0),
        ],
    ),
    "embedding": ModelTypeParams(
        config_fields=[
            ParamField(key="dimensions", label="向量维度", type="number", default=1024),
            ParamField(key="max_input_tokens", label="最大输入 Token", type="number", default=8192),
        ],
        invocation_params=[],
    ),
    "rerank": ModelTypeParams(
        config_fields=[
            ParamField(key="max_input_tokens", label="最大输入 Token", type="number", default=4096),
        ],
        invocation_params=[
            ParamField(key="top_n", label="Top N", type="number", min=1, default=10),
        ],
    ),
}
