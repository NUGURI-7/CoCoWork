"""Workspace 运行时：外层 StateGraph + 内置 Supervisor。

把 workspace 的「内置管家」(supervisor) 装配成一张可流式的图，交给
runtime.run_chat_stream 跑。与 Playground 的三点差异：

- supervisor 不走模板链：它是工作空间自带的通用内置 loop，直接 create_agent 拼，
  跟 templates/(给用户建的 NPC 用)无关。
- 外面套一层薄 StateGraph 持 workspace 级数据：supervisor 作为其中唯一节点。
- 返回形态与 prepare_stream 一致 (CompiledStateGraph, list[BaseMessage])，
  stream 端点 ⑤⑥ plumbing + Playground 全部零改。
"""
from datetime import date
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
from langchain_core.messages import BaseMessage, HumanMessage
from app.models import User, Workspace, WorkspaceMember, Message, KnowledgeBase, MCPServer
from app.agents.workspace.view_context_assembler import ViewContextAssembler, Viewer, SPEAKER_SUPERVISOR
from app.models import SenderKind
from app.agents.runtime.runner import (
    assemble_tools,
    build_chat_model,
    to_lc_messages,
)
from app.core.exceptions import ValidationException
from app.models import User, Workspace, WorkspaceMember
from app.schemas.agent.chat_schema import ChatStreamRequest
from app.schemas.agent.config_schema import AgentConfig
from app.tools import resolve_tools


def _workspace_base_prompt(
    workspace_name: str, member_names: list[str], self_name: str
) -> str:
    """workspace 协作框架 —— supervisor / member 共享的出场底座。

    拼在应答者自己的人设之前。含空间名 / 成员名单 / 日期、应答者自我身份
    (self_name 与 assembler 打的 <msg from> 标签同名，应答者据此认出对自己的引用)，
    以及读 / 写 <msg> 标签的约定。
    """
    roster = "、".join(member_names) if member_names else "（暂无其他成员）"
    today = date.today().isoformat()
    return (
        f"你在多成员协作的工作空间「{workspace_name}」，成员：{roster}。今天是 {today}。\n"
        f'你在这里的身份是「{self_name}」——别人提到 {self_name}、或标 <msg from="{self_name}"> 时，指的就是你。\n'
        '历史里 <msg from="X">…</msg> 是 X 的发言，无标签的是人类用户的发言。\n'
        "回复时直接正常说话，不要自己带 <msg> 标签。\n"
    )


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
        f"{base_prompt}\n\n{DEFAULT_SUBAGENT_PROMPT}"
        if base_prompt else DEFAULT_SUBAGENT_PROMPT
    )

    profile = await build_capability_profile(member_cfg, user)

    runnable = create_agent(
        model=model,
        tools=tools,
        system_prompt=system_prompt,
    )

    desc = f"{agent.name}：{agent.description}" if agent.description else agent.name
    return {
        "name": f"member_{member.id.hex[:8]}",
        "description": f"{desc}\n能力 · {profile}",
        "runnable": runnable,
    }

async def build_capability_profile(cfg: AgentConfig, user: User) -> str:
    """从 config 派生一行能力画像 —— 供 Supervisor 按能力路由。

    只取 MCP/KB/内置工具的「名字标签」，不碰工具 schema：
    路由层要的是「这成员挂了高德地图」，不是工具的参数细节。
    画像长度随挂载项数增长，与单个 MCP 暴露多少工具无关。
    """
    tags: list[str] = []

    builtin = [t.name for t in resolve_tools(cfg.builtin_tools)]
    if builtin:
        tags.append(f"内置[{','.join(builtin)}]")

    if cfg.knowledge:
        kbs = await KnowledgeBase.filter(id__in=cfg.knowledge, created_by=user)
        if kbs:
            tags.append(f"知识库[{','.join(kb.name for kb in kbs)}]")

    if cfg.mcp_servers:
        servers = await MCPServer.filter(
            id__in=cfg.mcp_servers, created_by=user, enabled=True
        )
        if servers:
            tags.append(f"MCP[{','.join(s.name for s in servers)}]")

    return " · ".join(tags) if tags else "无挂载工具"


async def build_workspace_graph(
        workspace: Workspace,
        request: ChatStreamRequest,
        user: User,
        past: list[Message],  # ← 新增:DB 历史消息(视角化用)
        responder: WorkspaceMember | None = None,  # None = supervisor;否则 = 被 @ 的成员
) -> tuple[CompiledStateGraph, list[BaseMessage]]:
    """装配 workspace 对话图 —— 内置 supervisor 套外层 StateGraph。

        与 prepare_stream 同形态返回 (graph, messages)，供 run_chat_stream 直接消费。
        所有可能 raise 的逻辑在此完成 —— FastAPI handler 接 ValidationException → 400 JSON，
        此刻 SSE 还没起。

        Args:
            workspace: 已取出的 Workspace 实例(supervisor jsonb 在 workspace.supervisor)
            request:   当前轮 user 输入 + 历史(历史由 stream 端点从 DB 拼好)
            user:      当前用户(KB 工具归属校验用)
            past:      新增:DB 历史消息(视角化用)
            responder: None = supervisor;否则 = 被 @ 的成员

        Raises:
            ValidationException: supervisor 未配 chat 模型 / 槽位类型错 / 模型不存在
    """


    # 拉本 workspace 招募的成员（select_related agent —— 正向 FK 走 JOIN，一次查询）
    members = await WorkspaceMember.filter(
        workspace_id=workspace.id
    ).select_related("agent")

    member_names = {m.id: m.agent.name for m in members}

    # 根据 responder 定三件事:用谁的 config、什么视角、能不能派活

    if responder is None:
        cfg = AgentConfig.model_validate(workspace.supervisor)
        viewer = Viewer(sender_kind=SenderKind.SUPERVISOR)
        can_delegate = True
        self_name = SPEAKER_SUPERVISOR # 与 assembler 打的 from 标签同源
    else:
        cfg = AgentConfig.model_validate(responder.agent.config)
        viewer = Viewer(sender_kind=SenderKind.MEMBER, member_id=responder.id)
        can_delegate = False # @直连成员不派活
        self_name = responder.agent.name # 成员用 agent.name，同样与 from 标签同源

    if cfg.models.chat is None:
        raise ValidationException("应答者未配置 chat 模型")

    chat_model = await build_chat_model(cfg.models.chat)
    tools = await assemble_tools(cfg, user)

    # base 框架(协议说明 + 名单 + 日期 + 应答者自我身份)+ 应答者自己的人设
    base = _workspace_base_prompt(workspace.name, list(member_names.values()), self_name)

    system_prompt = f"{base}\n{cfg.system_prompt}" if cfg.system_prompt else base

    # 派活 middleware 只有 supervisor 挂
    middleware: list[AgentMiddleware] = [WorkspaceContextMiddleware()]
    if can_delegate:
        subagents = [
            await _member_to_subagent(member, user, chat_model)
            for member in members
        ]
        if subagents:
            middleware.append(
                SubAgentMiddleware(backend=StateBackend(), subagents=subagents)
            )

    responder_agent = create_agent(
        model=chat_model,
        tools=tools,
        system_prompt=system_prompt,
        middleware=middleware
    )

    # 外层薄图：supervisor 作唯一节点，START → supervisor → END
    builder = StateGraph(WorkspaceState)

    builder.add_node("supervisor", responder_agent)
    builder.add_edge(START, "supervisor")
    builder.add_edge("supervisor", END)
    graph = builder.compile()

    # 视角化历史(viewer 跟着应答者走)+ 当前轮 user 输入
    history = await ViewContextAssembler().build(past, viewer, member_names)
    messages = history + to_lc_messages([], request.content)

    return graph, messages
