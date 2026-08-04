"""开放网页搜索 —— 免费公开搜索引擎（ddgs 聚合）。

**定位要说在前面：这不是生产选型。** 免费公开渠道会限流、无 SLA、无合同，
真实产品做联网搜索一律走 Tavily / Brave / Serper / Bing 这类带 key 的商用 API。
它在本项目的位置是「零配置兜底」—— clone 本项目的人什么都不配，就能把
Retrieve-then-Read 这类需要数据源的模板跑起来。等工具凭证那套落地、Tavily 上来
当正主之后，这个退回备胎，不删。

backend 用库默认的 "auto"（在 duckduckgo / google / brave / mojeek / startpage /
yahoo / yandex 等 9 个免费引擎之间自动选择与回退），不钉死某一家：单一免费引擎
太容易被限流，聚合互相兜底才勉强可用 —— 这正是 ddgs 这个库存在的理由。工具名
因此也不绑定任何一家，未来带 key 的 tavily_search / brave_search 各叫各的。
"""

import asyncio
from typing import Any

from ddgs import DDGS
from pydantic import BaseModel, Field

from app.tools.base import CoCoTool, ToolCategory
from app.tools.registry import register_tool

# 单次返回条数。不开放给 LLM 调 —— 同 KnowledgeRetrievalTool 的 default_top_k：
# 条数是上下文预算问题，属于工具作者的决定，不是模型该临场发挥的参数
_MAX_RESULTS = 5

# 地域偏好。"wt-wt" = worldwide，无地域倾向；库默认的 "us-en" 会把结果往英文世界
# 压，中文查询命中率明显更差
_REGION = "wt-wt"


def _search(query: str) -> list[dict[str, Any]]:
    """同步检索。整个函数丢进线程执行，连 DDGS() 构造一起 —— 见 _execute。"""
    return DDGS().text(query, max_results=_MAX_RESULTS, region=_REGION)


class OpenWebSearchInput(BaseModel):
    query: str = Field(
        ...,
        description="搜索关键词。用陈述式短语而非整句问句，命中率更高。",
    )


@register_tool
class OpenWebSearchTool(CoCoTool):
    name: str = "open_web_search"
    display_name: str = "网页搜索"
    category: ToolCategory = "data_source"
    description: str = (
        "在公开网络上搜索，返回若干条结果的标题、链接与摘要。"
        "需要查证事实、获取时效性信息、或回答训练数据里没有的内容时使用。"
        "注意返回的是搜索结果摘要，不是网页全文。"
    )
    args_schema: type[BaseModel] = OpenWebSearchInput

    async def _execute(self, query: str) -> str:
        # ddgs 只有同步 API，且内部会自建 asyncio loop 做结果缓存 —— 在事件循环里
        # 直接调用会把整个循环堵死。丢进线程（同 storage 那边包 boto3 的路子），
        # 连 DDGS() 构造一起进去，不在主线程碰它的任何东西
        results = await asyncio.to_thread(_search, query)

        if not results:
            # 明确说「没查到」而不是返回空串 —— 下游模板的 prompt 要求「查不到就
            # 如实说」，模型得先能看出这次是空手而归
            return f"搜索「{query}」没有找到任何结果。"

        # href = 结果链接，body = 摘要片段（ddgs 的原始字段名，不改）
        return "\n\n".join(
            f"{i}. {r.get('title', '')}\n{r.get('href', '')}\n{r.get('body', '')}"
            for i, r in enumerate(results, 1)
        )
