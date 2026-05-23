from tortoise import fields

from app.models.base import UUIDBaseModel


class ProviderModelCatalog(UUIDBaseModel):
    """供应商可用模型目录。

    管理员维护，定义每个 provider_type 下可选的模型列表。
    普通用户创建 AIModel 实例时从此目录中选择。
    纯配置数据，不参与业务流程。
    """

    provider_type = fields.CharField(max_length=50, description="供应商类型")
    model_id = fields.CharField(max_length=100, description="上游模型标识")
    model_type = fields.CharField(max_length=20, description="chat / embedding / rerank")

    class Meta:
        table = "provider_model_catalog"
        unique_together = (("provider_type", "model_id"),)
