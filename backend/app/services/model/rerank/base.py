from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RerankHit:
    """单条精排结果。

    - `index`：指向入参 documents 列表的下标（谁被打的分）
    - `score`：相关性分，各实现负责归一到 [0,1]，降序可比
    """

    index: int
    score: float


class BaseRerankClient(ABC):
    """Rerank 客户端抽象基类。

    Rerank 无行业统一协议，子类按 provider 的 API 形状实现，
    负责把各家请求/响应翻译成统一契约：documents 下标 + [0,1] 相关性分。
    连通性失败等异常不在此层包装，由调用方按场景处理。
    """

    @abstractmethod
    async def rerank(
        self,
        base_url: str,
        api_key: str,
        model_name: str,
        query: str,
        documents: list[str],
        top_n: int | None = None,
    ) -> list[RerankHit]:
        """对 documents 按与 query 的相关性打分，降序返回。

        Args:
            api_key: 明文 API Key（可为空串，空 Key 时不带鉴权头）
            top_n: 只返回前 n 条；None 返回全部。
        """