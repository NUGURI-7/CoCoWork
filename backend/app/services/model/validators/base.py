from abc import ABC, abstractmethod
from typing import Any

from app.services.model.credentials import BaseCredentials


class BaseModelValidator(ABC):
    """模型连通性验证抽象基类。

    子类按 provider_type + model_type 实现具体的验证逻辑，
    并自行决定运输层（OpenAI SDK / 裸 HTTP 等）。
    验证通过返回探测到的模型固有信息（无则 {}），失败抛异常。
    """

    @abstractmethod
    async def validate(
            self, base_url: str, credentials: BaseCredentials, model_name: str,
    ) -> dict[str, Any]:
        """发送最小请求验证模型可用性，并顺带探测固有信息。

        Args:
            base_url: 上游服务地址
            credentials: 明文凭证包，字段随 provider_type 而定（空 Key 语义由各运输层处理）
            model_name: 上游模型标识

        Returns:
            探测到的模型固有信息（如 embedding 维度），没有则空 dict。

        Raises:
            ValidationException: 验证失败
        """