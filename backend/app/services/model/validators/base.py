from abc import ABC, abstractmethod
from typing import Any

from openai import AsyncOpenAI


class BaseModelValidator(ABC):
    """模型连通性验证抽象基类。

    子类按 provider_type + model_type 实现具体的验证逻辑。
    验证通过返回探测到的模型固有信息（无则 {}），失败抛异常。
    """

    @abstractmethod
    async def validate(self, client: AsyncOpenAI, model_name: str) -> dict[str, Any]:
        """发送最小请求验证模型可用性，并顺带探测固有信息。

        Args:
            client: 已构建好的 OpenAI 兼容客户端
            model_name: 上游模型标识

        Returns:
            探测到的模型固有信息（如 embedding 维度），没有则空 dict。

        Raises:
            ValidationException: 验证失败
        """
