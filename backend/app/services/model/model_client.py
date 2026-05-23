"""统一 OpenAI 兼容客户端。

基于 openai SDK 的 base_url 参数，天然兼容阿里百炼 / DeepSeek / 硅基流动等服务。
Rerank 不走 OpenAI 协议，留到 RAG 阶段；LangChain 桥接留到 Agent 阶段。
"""

import logging
from typing import Any

from openai import AsyncOpenAI

from app.core.encryption import decrypt
from app.models.model import AIModel

logger = logging.getLogger(__name__)


class ModelClient:
    """从 Provider + AIModel 记录构造 openai 客户端并发起调用。"""

    @staticmethod
    def build_client(base_url: str, api_key: str) -> AsyncOpenAI:
        """构建 OpenAI 兼容客户端。Validator 和业务调用共用此方法。"""
        return AsyncOpenAI(api_key=api_key, base_url=base_url)

    @staticmethod
    def _resolve_credentials(model: AIModel) -> tuple[str, str]:
        """解析实际使用的 base_url 和 api_key（Model 级优先，fallback Provider 级）。"""
        base_url = model.base_url or model.provider.base_url
        api_key_encrypted = model.api_key_encrypted or model.provider.api_key_encrypted
        return base_url, decrypt(api_key_encrypted)

    @classmethod
    def get_model_client(cls, model: AIModel) -> AsyncOpenAI:
        """从 AIModel 构造客户端（含 fallback 逻辑）。"""
        base_url, api_key = cls._resolve_credentials(model)
        return cls.build_client(base_url, api_key)

    @classmethod
    async def chat_completion(
        cls,
        model: AIModel,
        messages: list[dict[str, str]],
        **params: Any,
    ):
        """调用 chat completions。"""
        client = cls.get_model_client(model)
        return await client.chat.completions.create(
            model=model.model_name,
            messages=messages,
            **params,
        )

    @classmethod
    async def create_embedding(
        cls,
        model: AIModel,
        texts: list[str],
        **params: Any,
    ) -> list[list[float]]:
        """调用 embeddings，返回向量列表。"""
        client = cls.get_model_client(model)
        response = await client.embeddings.create(
            model=model.model_name,
            input=texts,
            **params,
        )
        return [item.embedding for item in response.data]
