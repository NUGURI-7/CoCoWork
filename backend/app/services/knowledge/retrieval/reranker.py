"""精排后置阶段：对粗排候选用 rerank 模型重打分。

不是第四种检索 mode，而是调度层检索之后的后处理阶段，管线四步：
粗排（阈值置 0、窗口放大）→ 本模块打分 → 阈值过滤 → 截 top_k。
打分后 hit.score 被 rerank 相关性分整体替换（[0,1] 校准分，全场唯一
有资格做硬过滤的分数）；matched_by 等其余字段原样保留。
"""

import logging

from app.models import AIModel
from app.schemas.knowledge import RetrievalHit
from app.services.model.model_client import ModelClient
from app.services.model.rerank import get_rerank_client

logger = logging.getLogger(__name__)

# 精排窗口 = top_k × FACTOR，封顶 CAP。粗排多交货、精排挑尖子；
# 与 vector 的 CANDIDATE_FACTOR、hybrid 的 HYBRID_LEG_FACTOR 同族第三例。
RERANK_CANDIDATE_FACTOR = 10
RERANK_CANDIDATE_CAP = 100

def rerank_window(top_k: int) -> int:
    """开启精排时粗排的交货量（调度层用它放大粗排 top_k）。"""
    return min(top_k * RERANK_CANDIDATE_FACTOR, RERANK_CANDIDATE_CAP)

async def rerank_hits(
    model: AIModel,
    query: str,
    hits: list[RetrievalHit],
    top_k: int,
    similarity_threshold: float,
) -> list[RetrievalHit]:
    """对候选 hits 精排：打分 → 替换 score → 阈值过滤 → 截 top_k。

    Args:
        model: rerank 类型 AIModel（调度层已完成归属/类型校验并 prefetch provider）
        hits: 粗排候选（阈值置 0 捞出的全量窗口）
        similarity_threshold: 作用在 rerank 分上（过滤权归精排，粗排不卡分）

    Raises:
        httpx.HTTPError: 上游调用失败原样冒泡，由调用方决定处置
    """
    if not hits:
        return hits

    base_url, api_key = ModelClient.resolve_credentials(model)
    client = get_rerank_client(model.provider.provider_type)
    scored = await client.rerank(
        base_url=base_url,
        api_key=api_key,
        model_name=model.model_name,
        query=query,
        # 送交货单元 content：keyword 路命中无 chunk_text，且 reranker 评的
        # 正是「这段交给 LLM 值不值」；超长段由上游按窗口切块取最高块分
        documents=[hit.content for hit in hits],
        top_n=top_k,
    )

    reranked: list[RetrievalHit] = []
    for item in scored:
        if item.score < similarity_threshold:
            break  # scored 降序，首个低于阈值处直接收工
        hit = hits[item.index]
        hit.score = item.score
        reranked.append(hit)
    return reranked



