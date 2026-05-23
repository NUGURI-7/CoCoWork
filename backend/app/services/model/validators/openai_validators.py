import logging

from openai import AsyncOpenAI

from app.core.exceptions.types import ValidationException
from app.services.model.validators.base import BaseModelValidator

logger = logging.getLogger(__name__)


class OpenAIChatValidator(BaseModelValidator):
    """OpenAI 兼容供应商的 Chat 模型验证。"""

    async def validate(self, client: AsyncOpenAI, model_name: str) -> None:
        try:
            await client.chat.completions.create(
                model=model_name,
                messages=[{"role": "user", "content": "hi"}],
                max_tokens=1,
            )
        except Exception as e:
            logger.warning("Chat 模型验证失败: %s %s", model_name, e)
            raise ValidationException(
                f"模型 '{model_name}' 连通性验证失败: {e}",
            ) from e


class OpenAIEmbeddingValidator(BaseModelValidator):
    """OpenAI 兼容供应商的 Embedding 模型验证。"""

    async def validate(self, client: AsyncOpenAI, model_name: str) -> None:
        try:
            await client.embeddings.create(
                model=model_name,
                input=["test"],
            )
        except Exception as e:
            logger.warning("Embedding 模型验证失败: %s %s", model_name, e)
            raise ValidationException(
                f"模型 '{model_name}' 连通性验证失败: {e}",
            ) from e
