"""检索模块对外入口：策略 dispatch + Retriever ABC。

调用方只 `from app.services.knowledge.retrieval import RetrievalService, RetrievalParams`，
不感知具体 retriever 实现。
扩 mode = 子包内新建 retriever 文件 + service.py 调度表加一行，对外契约不变。
"""

from app.services.knowledge.retrieval.base import (
    RetrievalMode,
    RetrievalParams,
    RetrievalResult,
    Retriever,
)
from app.services.knowledge.retrieval.service import (
    RetrievalService,
    get_retrieval_service,
)

__all__ = [
    "RetrievalMode",
    "RetrievalParams",
    "RetrievalResult",
    "Retriever",
    "RetrievalService",
    "get_retrieval_service",
]