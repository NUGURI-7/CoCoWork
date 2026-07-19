import logging
from typing import Any

import httpx

from app.services.model.rerank.base import BaseRerankClient, RerankHit

logger = logging.getLogger(__name__)

# 精排窗口封顶 100 条时的调用余量；单次请求超时
_RERANK_TIMEOUT_S = 30.0


class CohereRerankClient(BaseRerankClient):
    """Cohere 形状（事实标准扁平 payload）的 rerank 客户端。

    覆盖硅基流动 / Jina / Cohere 等同形供应商：
    POST {base_url}/rerank，请求 {model, query, documents, top_n}，
    响应 results[].{index, relevance_score}（上游已降序）。
    """

    async def rerank(
        self,
        base_url: str,
        api_key: str,
        model_name: str,
        query: str,
        documents: list[str],
        top_n: int | None = None,
    ) -> list[RerankHit]:

        payload: dict[str, Any] = {
            "model": model_name,
            "query": query,
            "documents": documents,
            # 只要下标和分数，不让上游回传原文（省带宽，原文调用方自己有）
            "return_documents": False,
        }

        if top_n is not None:
            payload["top_n"] = top_n

        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        url = f"{base_url.rstrip('/')}/rerank"

        async with httpx.AsyncClient(timeout=_RERANK_TIMEOUT_S) as client:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()

            data = resp.json()

        hits = [
            RerankHit(index=item["index"], score=float(item["relevance_score"]))
            for item in data["results"]
        ]
        # 上游约定降序，这里按自身契约再保证一次
        hits.sort(key=lambda h: h.score, reverse=True)
        return hits