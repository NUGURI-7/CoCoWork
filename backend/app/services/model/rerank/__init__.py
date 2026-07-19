from app.services.model.rerank.base import BaseRerankClient, RerankHit
from app.services.model.rerank.cohere_rerank import CohereRerankClient

# Rerank 没有统一协议，但 Cohere 形状是事实标准多数派，作 default 兜底
_default: BaseRerankClient = CohereRerankClient()

_overrides: dict[str, BaseRerankClient] = {
    # "dashscope": DashScopeRerankClient(),  # 老接口嵌套形状，接入时再补
}


def get_rerank_client(provider_type: str) -> BaseRerankClient:
    """按 provider_type 查找 rerank 客户端：overrides 精确匹配 → Cohere 形状兜底。"""
    return _overrides.get(provider_type, _default)