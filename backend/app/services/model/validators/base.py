from abc import ABC, abstractmethod

from openai import AsyncOpenAI


class BaseModelValidator(ABC):
    """模型连通性验证抽象基类。

    子类按 provider_type + model_type 实现具体的验证逻辑。
    验证通过无返回，失败抛异常。
    """

    @abstractmethod
    async def validate(self, client: AsyncOpenAI, model_name: str) -> None:
        """发送最小请求验证模型可用性。

        Args:
            client: 已构建好的 OpenAI 兼容客户端
            model_name: 上游模型标识

        Raises:
            ValidationException: 验证失败
        """
