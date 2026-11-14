"""Agent 的可见与可用规则 —— 所有「这个人能不能看到 / 用这个 Agent」的判断都走这里。

两类 Agent，规则不同：
- **自己建的**：只有自己能看、能用；启用开关对它不生效。用通用模板建的都属于这类，管理员建的也一样
- **公共 Agent**（管理员用业务模板建的）：启用时所有人能看、能用；停用后只对聊过它的人可见
  （标「已下线」），任何人都不能再发消息。管理员始终能看到所有公共 Agent

查询条件拼成 Q 表达式进 WHERE，而不是查出来再在内存里筛 —— 归属条件进得了 SQL，
就不存在「查到了但忘了判权限」这个状态。
"""

from uuid import UUID

from tortoise.expressions import Q, Subquery

from app.agents.templates import list_templates
from app.core.exceptions import Conflict409, NotFound404
from app.models import Agent, Conversation, User


def _business_template_keys() -> list[str]:
    return [t.key for t in list_templates() if t.category == "business"]


def _visible_filter(user: User) -> Q:
    """能看到的 Agent：自己建的 + 公共 Agent（管理员用业务模板建的）中已启用的或自己聊过的。

    用通用模板建的 Agent 只归建的人，管理员建的也一样。
    """
    shared = Q(created_by__is_admin=True, template__in=_business_template_keys())
    if user.is_admin:
        return Q(created_by_id=user.id) | shared
    chatted = Q(id__in=Subquery(
        Conversation.filter(created_by_id=user.id, agent_id__isnull=False).values("agent_id")
    ))
    return Q(created_by_id=user.id) | (shared & (Q(is_enabled=True) | chatted))


def is_usable(agent: Agent, user: User) -> bool:
    """能不能发消息：自己建的，或管理员建的且已启用。

    调用方传入的 agent 必须已经过可见性过滤（且 select_related 了 created_by）。
    """
    return agent.created_by_id == user.id or agent.is_enabled


async def list_visible_agents(user: User) -> list[Agent]:
    """侧栏 Agent 选择器的数据源，按创建时间倒序。"""
    return (
        await Agent.filter(_visible_filter(user))
        .select_related("created_by")
        .order_by("-created_at")
    )


async def get_visible_agent(user: User, agent_id: UUID) -> Agent:
    """能看到才返回；看不到一律 404，不区分「不存在」和「无权限」。"""
    agent = (
        await Agent.filter(Q(id=agent_id) & _visible_filter(user))
        .select_related("created_by")
        .first()
    )
    if agent is None:
        raise NotFound404("Agent 不存在")
    return agent


async def get_usable_agent(user: User, agent_id: UUID) -> Agent:
    """能发消息才返回。看得到但已停用 → 409「已下线」，前端据此置灰输入框。"""
    agent = await get_visible_agent(user, agent_id)
    if not is_usable(agent, user):
        raise Conflict409("该 Agent 已下线")
    return agent
