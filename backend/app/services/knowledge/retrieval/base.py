"""检索策略抽象：mode + Retriever ABC + 统一参数/结果契约。

策略模式 + dispatch：新增检索模式 = 新建实现文件
+ enum 加一行 + service 调度表加一行，调用方零改动。
已实装 vector / keyword；hybrid 留待 v2。
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field

from app.models import KnowledgeBase
from app.schemas.knowledge import RetrievalHit


class RetrievalMode(StrEnum):
    """检索模式（扩 mode 时此处加值）。"""
    VECTOR = "vector"
    KEYWORD = "keyword"
    HYBRID = "hybrid"


class RetrievalParams(BaseModel):
    """检索请求参数（命中测试 / KB tool 等所有 caller 共用）。

    跨 mode 共用字段在这；某 mode 私有参数（如 hybrid 的 vector_weight）
    扩 mode 时再加 Optional 字段（默认 None，无关 mode 不受影响）。
    """
    query: str = Field(min_length=1, max_length=2000, description="查询文本")
    top_k: int = Field(default=5, ge=1, le=50, description="返回命中段数")
    similarity_threshold: float = Field(
        default=0.0, ge=0.0, le=1.0,
        description="相似度阈值，低于此分的命中不返回；默认 0 = 不过滤",
    )
    mode: RetrievalMode = Field(default=RetrievalMode.VECTOR, description="检索模式")
    vector_weight: float = Field(
        default=0.9, ge=0.0, le=1.0,
        description="hybrid 专用：向量路票权（关键词路 = 1-此值），其他 mode 忽略；"
                    "默认 0.9 = 基准五点扫描最优（2026-07-18，recall@10 0.804 唯一超纯向量点）",
    )
    rerank_model_id: UUID | None = Field(
        default=None,
        description="精排模型 id；非空即开启两级管线（粗排窗口放大+阈值移交精排），"
                    "None = 单级检索、行为与既往完全一致",
    )


@dataclass(slots=True)
class RetrievalResult:
    """检索响应：命中列表 + 各阶段耗时。

    timings 的 key 由具体 retriever 决定——vector 给 {embed_ms, search_ms}，
    将来 hybrid 给 {embed_ms, vector_ms, keyword_ms, fusion_ms} 等。
    上层组装时按需读，缺失 key 当 0 处理（不同 mode timings 形态不同是预期的）。
    """
    hits: list[RetrievalHit]
    timings: dict[str, float] = field(default_factory=dict)


class Retriever(ABC):
    """检索策略抽象。

    实现类只关注「拿 KB + params，返 hits + timings」。
    归属校验、总耗时、上层 Out 组装都在调度层（RetrievalService）做。
    """

    mode: RetrievalMode  # 子类类属性，声明本实现服务哪个 mode

    @abstractmethod
    async def retrieve(self, kb: KnowledgeBase, params: RetrievalParams) -> RetrievalResult:
        """执行检索。

        Args:
            kb: 调度层已校验归属并 prefetch embedding_model__provider 的 KB 实例
            params: 查询参数

        Returns:
            RetrievalResult（hits + timings dict）
        """
        ...
