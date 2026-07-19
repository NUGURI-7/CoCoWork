"""检索调度入口：策略 dispatch + 归属校验 + 总耗时。

按 params.mode 路由到具体 Retriever 实现；归属校验、KB 取、外圈总耗时
统一在这层做，retriever 只关注算法实现。
"""
import time
from uuid import UUID

from app.core.exceptions import NotFound404
from app.models import KnowledgeBase, User
from app.services.knowledge.retrieval.base import (
    RetrievalMode,
    RetrievalParams,
    RetrievalResult,
    Retriever,
)
from app.services.knowledge.retrieval.hybrid import HybridRetriever
from app.services.knowledge.retrieval.keyword import KeywordRetriever
from app.services.knowledge.retrieval.vector import VectorRetriever
from app.models import AIModel
from app.services.knowledge.retrieval.reranker import rerank_hits, rerank_window


class RetrievalService:
    """检索通用入口（命中测试 / KB tool / 其他场景共用）。

    扩 mode = 新建 retriever 文件 + 在 _RETRIEVERS 加一行，调用方零改动。
    """

    _RETRIEVERS: dict[RetrievalMode, Retriever] = {
        VectorRetriever.mode: VectorRetriever(),
        KeywordRetriever.mode: KeywordRetriever(),
        HybridRetriever.mode: HybridRetriever(),
    }

    async def retrieve(
            self,
            user: User,
            kb_id: UUID,
            params: RetrievalParams,
    ) -> RetrievalResult:
        """检索（按 params.mode 调度）。

                Returns:
                    RetrievalResult（hits + timings：含 retriever 细分耗时 + total_ms）

                Raises:
                    NotFound404: 知识库不存在或不归当前用户
                    ValueError: 未注册的 mode（扩 enum 但漏配 retriever 时 fail fast）
        """
        # 1. 归属校验 + 拿到 embedding 模型（带 provider 用于解析凭证）
        kb = await (
            KnowledgeBase
            .filter(id=kb_id, created_by=user)
            .prefetch_related("embedding_model__provider")
            .first()
        )
        if kb is None:
            raise NotFound404("知识库不存在")

        # 2. dispatch 到具体 retriever
        retriever = self._RETRIEVERS.get(params.mode)
        if retriever is None:
            raise ValueError(f"未注册的检索模式：{params.mode}")

        # 3. 执行 + 外圈总耗时（不含归属校验，跟老代码 total_ms 语义对齐）
        t0 = time.perf_counter()
        if params.rerank_model_id is None:
            # 单级：行为与既往完全一致
            result = await retriever.retrieve(kb, params)
        else:
            # 两级：粗排（窗口放大 + 阈值置 0，过滤权移交精排）→ 精排
            rerank_model = await self._get_rerank_model(user, params.rerank_model_id)

            coarse_params = params.model_copy(update={
                "top_k": rerank_window(params.top_k),
                "similarity_threshold": 0.0,
            })
            result = await retriever.retrieve(kb, coarse_params)

            t_rerank = time.perf_counter()
            result.hits = await rerank_hits(
                model=rerank_model,
                query=params.query,
                hits=result.hits,
                top_k=params.top_k,
                similarity_threshold=params.similarity_threshold,
            )
            result.timings["rerank_ms"] = round((time.perf_counter() - t_rerank) * 1000, 1)

        t1 = time.perf_counter()
        result.timings["total_ms"] = round((t1 - t0) * 1000, 1)
        return result

    @staticmethod
    async def _get_rerank_model(user: User, model_id: UUID) -> AIModel:
        """取 rerank 模型：归属 + 类型 + 启用三重校验，带 provider 供解析凭证。"""
        model = await (
            AIModel
            .filter(
                id=model_id,
                model_type="rerank",
                is_enabled=True,
                provider__created_by=user,
            )
            .prefetch_related("provider")
            .first()
        )
        if model is None:
            raise NotFound404("Rerank 模型不存在或不可用")
        return model


async def get_retrieval_service() -> RetrievalService:
    return RetrievalService()
