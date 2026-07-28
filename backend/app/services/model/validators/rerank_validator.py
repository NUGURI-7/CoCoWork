import logging
from typing import Any

from app.core.exceptions.types import ValidationException
from app.services.model.credentials import BaseCredentials
from app.services.model.rerank.base import BaseRerankClient
from app.services.model.validators.base import BaseModelValidator

logger = logging.getLogger(__name__)

class RerankValidator(BaseModelValidator):
    """Rerank 模型验证：发一条最小重排请求验连通。

    验证逻辑与运输层解耦：具体 API 形状由注入的 rerank 客户端决定，
    新形状供应商复用本类、注册时换客户端即可。
    """

    def __init__(self, client: BaseRerankClient) -> None:
        self._client = client

    async def validate(self, base_url: str, credentials: BaseCredentials, model_name: str) -> dict[str, Any]:
        try:
            await self._client.rerank(
                base_url=base_url,
                api_key=credentials.api_key,
                model_name=model_name,
                query="hi",
                documents=["hello", "world"],
                top_n=1,
            )
        except Exception as e:
            logger.warning("Rerank 模型验证失败: %s %s", model_name, e)
            raise ValidationException(
                f"模型 '{model_name}' 连通性验证失败: {e}",
            ) from e
        return {}

