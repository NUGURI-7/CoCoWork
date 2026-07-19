import logging
from typing import Any

from app.core.exceptions.types import ValidationException
from app.services.model.model_client import ModelClient
from app.services.model.validators.base import BaseModelValidator

logger = logging.getLogger(__name__)


class OpenAIChatValidator(BaseModelValidator):
    """OpenAI 兼容供应商的 Chat 模型验证。"""

    async def validate(self, base_url: str, api_key: str, model_name: str) -> dict[str, Any]:
        client = ModelClient.build_client(base_url, api_key)
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
        return {}


class OpenAIEmbeddingValidator(BaseModelValidator):
    """OpenAI 兼容供应商的 Embedding 模型验证。"""

    async def validate(self, base_url: str, api_key: str, model_name: str) -> dict[str, Any]:
        client = ModelClient.build_client(base_url, api_key)
        try:
            resp = await client.embeddings.create(
                model=model_name,
                input=["test"],
            )
        except Exception as e:
            logger.warning("Embedding 模型验证失败: %s %s", model_name, e)
            raise ValidationException(
                f"模型 '{model_name}' 连通性验证失败: {e}",
            ) from e
        return {"embedding_dim": len(resp.data[0].embedding)}
