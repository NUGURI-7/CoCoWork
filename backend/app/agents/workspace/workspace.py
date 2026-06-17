"""Workspace 运行时：外层 StateGraph + 内置 Supervisor。

把 workspace 的「内置管家」(supervisor) 装配成一张可流式的图，交给
runtime.run_chat_stream 跑。与 Playground 的三点差异：

- supervisor 不走模板链：它是工作空间自带的通用内置 loop，直接 create_agent 拼，
  跟 templates/(给用户建的 NPC 用)无关。
- 外面套一层薄 StateGraph 持 workspace 级数据：supervisor 作为其中唯一节点。
- 返回形态与 prepare_stream 一致 (CompiledStateGraph, list[BaseMessage])，
  stream 端点 ⑤⑥ plumbing + Playground 全部零改。
"""
from typing import Annotated, TypedDict

from langchain.agents import create_agent
from langchain.agents.middleware import AgentMiddleware
from langchain_core.messages import BaseMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.graph.state import CompiledStateGraph
from langchain_core.language_models import BaseChatModel
from deepagents.middleware.subagents import CompiledSubAgent, DEFAULT_SUBAGENT_PROMPT
from deepagents import SubAgentMiddleware
from deepagents.backends import StateBackend

from app.agents.runtime.runner import (
    assemble_tools,
    build_chat_model,
    to_lc_messages,
)
from app.core.exceptions import ValidationException
from app.models import User, Workspace, WorkspaceMember
from app.schemas.agent.chat_schema import ChatStreamRequest
from app.schemas.agent.config_schema import AgentConfig


class WorkspaceState(TypedDict):
    """外层图里流动的共享数据。

    messages: 对话历史。add_messages reducer 负责「按 id 去重 + 追加」。
        外层 state 与 supervisor 内层 AgentState 通过同名 messages channel 自动对接
        (子图共享父图同名 state 键，子图直接读写父图的 channel)。
    """

    messages: Annotated[list, add_messages]


class WorkspaceContextMiddleware(AgentMiddleware):
    """workspace 级上下文注入点(方案 C 的接缝)。

    当前不覆写任何 hook = 透传。workspace 上下文(成员清单 / 共享记忆 / 工具可见性
    裁剪)将来在此接入，supervisor 的 create_agent 调用本身一字不动 —— 现在就挂上，
    是为了 workspace 阶段「填空即可」，而不是回头改装配主体。
    """


async def _member_to_subagent(
        member: WorkspaceMember,
        user: User,
        fallback_model: BaseChatModel,
) -> CompiledSubAgent:
    """把一个招募成员装配成 supervisor 可派活的子 agent。

    成员没配 chat 模型时继承 supervisor 的模型（fallback_model）——
    模型只决定「用哪个 LLM」，成员的身份（prompt / tools / 知识库）仍是它自己的；
    这也是 deepagents 的默认语义（subagent 不配 model 则继承主 agent）。
    """
    agent = member.agent
    member_cfg = AgentConfig.model_validate(agent.config)

    model = (
        await build_chat_model(member_cfg.models.chat)
        if member_cfg.models.chat is not None
        else fallback_model
    )
    tools = await assemble_tools(member_cfg, user)

    base_prompt = member_cfg.system_prompt
    system_prompt = (
        f"{base_prompt}\n\n{DEFAULT_SUBAGENT_PROMPT}"  # ← \n\n 隔开
        if base_prompt else DEFAULT_SUBAGENT_PROMPT
    )

    runnable = create_agent(
        model=model,
        tools=tools,
        system_prompt=system_prompt,
    )

    return {
        "name": f"member_{member.id.hex[:8]}",
        "description": f"{agent.name}：{agent.description or '无描述'}",
        "runnable": runnable,
    }


async def build_workspace_graph(
        workspace: Workspace,
        request: ChatStreamRequest,
        user: User
) -> tuple[CompiledStateGraph, list[BaseMessage]]:
    """装配 workspace 对话图 —— 内置 supervisor 套外层 StateGraph。

        与 prepare_stream 同形态返回 (graph, messages)，供 run_chat_stream 直接消费。
        所有可能 raise 的逻辑在此完成 —— FastAPI handler 接 ValidationException → 400 JSON，
        此刻 SSE 还没起。

        Args:
            workspace: 已取出的 Workspace 实例(supervisor jsonb 在 workspace.supervisor)
            request:   当前轮 user 输入 + 历史(历史由 stream 端点从 DB 拼好)
            user:      当前用户(KB 工具归属校验用)

        Raises:
            ValidationException: supervisor 未配 chat 模型 / 槽位类型错 / 模型不存在
    """

    cfg = AgentConfig.model_validate(workspace.supervisor)

    # 拉本 workspace 招募的成员（select_related agent —— 正向 FK 走 JOIN，一次查询）
    members = await WorkspaceMember.filter(
        workspace_id=workspace.id
    ).select_related("agent")

    if cfg.models.chat is None:
        raise ValidationException("Workspace 未配置 Supervisor 的 chat 模型")

    chat_model = await build_chat_model(cfg.models.chat)
    tools = await assemble_tools(cfg, user)

    # 招募成员 → 可派活的子 agent（没配模型的成员继承 supervisor 的 chat_model 兜底）
    subagents = [
        await _member_to_subagent(member, user, chat_model)
        for member in members
    ]
    # supervisor 的 middleware：上下文注入始终挂；派活仅在有成员时挂
    # （SubAgentMiddleware 的 subagents 不能为空，空会 raise）
    middleware: list[AgentMiddleware]= [WorkspaceContextMiddleware()]
    if subagents:
        middleware.append(
            SubAgentMiddleware(
                backend=StateBackend(),
                subagents=subagents
            )
        )

    # supervisor = 工作空间自带的通用内置 loop，直接拼，不走模板装配链
    supervisor = create_agent(
        model=chat_model,
        tools=tools,
        system_prompt=cfg.system_prompt,
        middleware=middleware,
    )

    # 外层薄图：supervisor 作唯一节点，START → supervisor → END
    builder = StateGraph(WorkspaceState)

    builder.add_node("supervisor", supervisor)
    builder.add_edge(START, "supervisor")
    builder.add_edge("supervisor", END)
    graph = builder.compile()

    messages = to_lc_messages(request.history, request.content)

    return graph, messages
