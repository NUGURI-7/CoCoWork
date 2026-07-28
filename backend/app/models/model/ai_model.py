from tortoise import fields

from app.models.base import TimestampMixin, UUIDBaseModel


class AIModel(UUIDBaseModel, TimestampMixin):
    """具体模型实例，挂在 Provider 下。

    - `model_name`：上游模型 ID（如 qwen-plus、text-embedding-v3）
    - `model_type`：chat / embedding / rerank
    - `config`：参数预设（temperature / top_p 等）
    - `base_url` / `credentials_encrypted`：可选覆盖，为空时 fallback 到 Provider 级
    """

    provider = fields.ForeignKeyField(
        "models.Provider", related_name="models", on_delete=fields.CASCADE,
    )
    model_name = fields.CharField(max_length=100, description="上游模型 ID")
    display_name = fields.CharField(max_length=100, description="前端展示名")
    model_type = fields.CharField(max_length=20, description="chat / embedding / rerank")
    config = fields.JSONField(default=dict, description="参数预设（temperature / top_p 等）")
    meta = fields.JSONField(default=dict, null=True, description="模型固有事实：dim / context_window / max_input 等（非用户可调）")
    base_url = fields.CharField(max_length=512, default="", description="覆盖 Provider 的 base URL（留空继承）")
    credentials_encrypted = fields.TextField(
        default="", description="整包覆盖 Provider 的凭证（留空继承）",
    )
    is_enabled = fields.BooleanField(default=True, description="是否启用")

    class Meta:
        table = "ai_models"
