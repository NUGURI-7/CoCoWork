from tortoise import fields

from app.models.base import TimestampMixin, UUIDBaseModel


class Provider(UUIDBaseModel, TimestampMixin):
    """上游模型服务供应商。

    - `created_by`：创建者
    - `credentials_encrypted`：加密的默认凭证包，模型实例可整包覆盖
    - `provider_type`：UI 标识（openai/dashscope/siliconflow/deepseek/anthropic/baidu/custom）
    """

    created_by = fields.ForeignKeyField(
        "models.User", related_name="providers", on_delete=fields.CASCADE,
    )
    name = fields.CharField(max_length=100, description="显示名")
    provider_type = fields.CharField(max_length=50, description="服务商类型")
    base_url = fields.CharField(max_length=512, description="默认 API base URL")
    credentials_encrypted = fields.TextField(
        description="凭证包：Fernet 加密的 JSON，形状见 services/model/credentials.py",
    )
    description = fields.CharField(max_length=500, default="", description="备注")

    class Meta:
        table = "providers"
