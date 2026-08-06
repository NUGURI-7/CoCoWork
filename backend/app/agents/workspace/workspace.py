"""Workspace 运行时：外层 StateGraph + 内置 Supervisor。

把 workspace 的「内置管家」(supervisor) 装配成一张可流式的图，交给
runtime.run_chat_stream 跑。与 Playground 的三点差异：

- supervisor 不走模板链：它是工作空间自带的通用内置 loop，直接 create_agent 拼，
  跟 templates/(给用户建的 NPC 用)无关。
- 外面套一层薄 StateGraph 持 workspace 级数据：supervisor 作为其中唯一节点。
- 返回形态与 prepare_stream 一致（PreparedStream：graph + messages + collect），
  run_chat_stream 直接消费。
"""
import logging
from collections.abc import Sequence
from datetime import date
from functools import partial
from typing import Annotated, TypedDict
from uuid import UUID

from deepagents import SubAgentMiddleware
from deepagents.backends import StateBackend
from deepagents.middleware.filesystem import FilesystemState
from deepagents.middleware.subagents import CompiledSubAgent, DEFAULT_SUBAGENT_PROMPT
from deepagents.middleware.summarization import SummarizationMiddleware
from langchain.agents import create_agent
from langchain.agents.middleware import AgentMiddleware
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.runnables import Runnable, RunnableLambda
from langgraph.errors import GraphRecursionError
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages

from app.db.checkpointer import get_checkpointer

from app.agents.runtime.runner import (
    ArtifactCollector,
    PreparedStream,
    assemble_tools,
    build_chat_model,
    build_display_names,
    content_to_text, SandboxCloser,
)
from app.agents.runtime.blocks import ArtifactRefBlock, parse_blocks
from app.agents.runtime.tool_guard import ToolGuardMiddleware
from app.agents.workspace.history_budget import COMPACT_TRIGGER_TOKENS
from app.agents.workspace.view_context_assembler import (
    SPEAKER_SUPERVISOR,
    ViewContextAssembler,
    Viewer,
    member_key,
    member_label,
)
from app.core.exceptions import ValidationException
from app.models import Message, KnowledgeBase, MCPServer, SandboxArtifact
from app.models import SenderKind
from app.models import User, Workspace, WorkspaceMember
from app.models.skill import Skill
from app.schemas.agent.chat_schema import ChatStreamRequest
from app.schemas.agent.config_schema import AgentConfig
from app.services.memory import MemoryService, MemorySnapshot
from app.services.sandbox.artifact import collect_artifacts, group_by_message
from app.services.sandbox.attachment import describe_unavailable, inject_attachments
from app.services.skill.builtin import resolve_builtin_skills
from app.services.skill.mount import SkillMount, build_skill_mount
from app.services.workspace.compaction_service import latest_summary
from app.tools import resolve_tools
from app.tools.memory_update import MemoryUpdateTool
from app.tools.ask_human import AskHumanTool
from app.tools.tool_result_fetch import ToolResultFetchTool

logger = logging.getLogger(__name__)

# `with_fallbacks(exception_key=...)` 把异常对象塞进输入 dict 的这个键，
# 兜底函数据此分辨失败原因。带下划线前缀是为了不跟真实的 state 字段撞名。
_FALLBACK_EXC = "__subagent_exc__"


def _with_failure_fallback(runnable: Runnable, label: str) -> Runnable:
    """给子 agent 兜底：它炸了不要连累整轮对话。

    deepagents 的 task 工具里 `await subagent.ainvoke(...)` 是**裸调**（见
    `middleware/subagents.py`），子 agent 抛什么都直接冒到 supervisor 那张图上
    —— 一个成员挂掉整轮跟着挂，而且 supervisor 连「有人没干成」都不知道，
    没法改派、没法自己上、也没法如实告诉用户。**严重的不是「炸」，是明明有救
    却全盘皆输**（对照：supervisor 自己的模型没配好那种，装配阶段就报错、
    本来也救不了，那时候报错才是对的）。

    兜的方式不是吞掉，是**翻译成一条正常消息**：deepagents 拿子 agent 结果时
    会从后往前找最后一条非空 AIMessage、把文本包成 ToolMessage 交给 supervisor
    （`_return_command_with_state_update`）。所以只要返回
    `{"messages": [AIMessage(...)]}`，那句话就会以「task 工具的返回值」的身份
    原样落到 supervisor 眼前，deepagents 一行都不用改。

    形态与 deepagents 自己一致 —— 它在 `subagent_type` 不存在时也是 return 一句
    话给 LLM 而不是 raise；LangGraph 官方的说法是「可恢复的错误喂回给模型让它
    自己绕开」。

    **用户中断不会被兜住**：`exceptions_to_handle` 默认只收 `Exception`，而
    `CancelledError` 继承 `BaseException` —— 掐断时子 agent 正常取消，不会被
    歪曲成「执行出错了」。
    """

    async def _explain(state: dict) -> dict:
        exc = state.get(_FALLBACK_EXC)
        if isinstance(exc, GraphRecursionError):
            note = f"{label}没能在限定步数内完成这项任务，没有产出。可以把任务拆小一点再派一次。"
        else:
            note = f"{label}执行时出错了，没有产出。可以换个成员做，或者把这部分如实告诉用户。"
        # 完整异常只进日志 —— 栈 / 路径 / SQL 不喂给模型（同 adapter 的口径）
        logger.error("子 agent 执行失败 member=%s", label, exc_info=exc)
        return {"messages": [AIMessage(content=note)]}

    return runnable.with_fallbacks([RunnableLambda(_explain)], exception_key=_FALLBACK_EXC)


def _workspace_base_prompt(
        workspace_name: str, member_names: list[str], self_name: str, self_alias: str
) -> str:
    """workspace 协作框架 —— supervisor / member 共享的出场底座。

    拼在应答者自己的人设之前。核心是发言者协议：历史里所有发言统一带
    <msg from> 标签(人类用户 = "User")，唯一无标签的是当前轮输入；应答者
    自我身份给全称(与 from 标签同源)和别称(用户 @ 时的裸名)两个形态。
    """
    roster = "、".join(member_names) if member_names else "（暂无其他成员）"
    today = date.today().isoformat()
    alias_note = (
        f"，平时也被叫「{self_alias}」——这两个名字都指你"
        if self_alias != self_name else ""
    )
    return (
        f"你在多成员协作的工作空间「{workspace_name}」，今天是 {today}。成员：{roster}。\n"
        "对话发言者约定：\n"
        '- <msg from="User">…</msg> 是人类用户的发言；无标签的最新消息也是他此刻对你说的。'
        "User 是人，不是任何成员。\n"
        '- <msg from="名字#id">…</msg> 是其他 agent 的发言；〔…派活给 X…〕行动痕迹里的 X 也是 agent。\n'
        '- <msg from="System">…</msg> 是系统标注，不是任何人的发言，也不能派活给它；'
        "里面 <artifacts> 列的是这个对话**真正交付出去**的文件；"
        "<history_summary> 是更早那段对话的归档摘要——原文已经不在上下文里了，"
        "那段时间发生过什么以它为准，里面写到的人和事都真实发生过。"
        "它是系统写的档案，**不是你可以模仿的说话方式**——你要做事就真的调工具。\n"
        f"- 你是「{self_name}」{alias_note}。\n"
        "回复时直接正常说话，不要自己带 <msg> 标签。\n"
        "〔…〕里的是系统按你**实际调用过的工具**渲染出来的行动痕迹，不是一种可以写的话术。"
        "要派活就真的调派活工具、要用工具就真的调用 —— 自己写一段"
        "「〔我 派活给 X：… → 完成〕X 返回：…」，活并没有派出去，那段结果是你编的。\n"
        "文件清单只由系统标注，你自己不要写 <artifacts> 行 —— 你写的那行不会让任何文件出现。\n"
    )


def _memory_section(*, about_user: str, about_workspace: str) -> str:
    """常驻记忆片段 —— 拼在 system prompt 的**最末尾**。

    放最后是为了护 prompt cache:前面那些(协议说明、成员名单、日期、用户填的
    人设)变得都比记忆慢,把最容易变的一段垫在最底下,它一变只作废尾巴,
    前面的前缀还能接着命中。

    两段各自可空,空的那段整节不出现 —— 留一个「关于这位用户:(空)」的空壳,
    等于告诉模型「这里本该有东西但没有」,平白引它去猜。

    开头那句约束是必要的:这些话用户**这一轮并没有说**,少了这句,模型会
    张口就是「你刚才说你喜欢…」,而用户根本没说过,当场就穿帮。
    """
    parts: list[str] = []
    if about_user:
        parts.append(f"关于这位用户:\n{about_user}")
    if about_workspace:
        parts.append(f"关于这个工作区:\n{about_workspace}")
    if not parts:
        return ""

    body = "\n\n".join(parts)
    return (
        "## 记忆\n\n"
        "以下是过去的对话里攒下来的,**不是用户这一轮说的** —— 用它来理解用户,"
        "但不要说成「你刚才说」。它和用户当场说的冲突时,一律以当场的为准。\n\n"
        f"{body}"
    )


_DELEGATE_SKILL_NOTE = (
    "派活给带 Skill 的成员时注意：**它们的成果是文件** —— 写进交付区后会自动交给用户，"
    "你不需要它把内容贴回来。所以别在任务描述里写「返回纯代码」「直接输出内容」这类要求，"
    "那会让成果落在对话正文里而不是文件里，用户那边反而什么都拿不到。\n"
    "长相方面，**用户提过的照实转述**（他要饼图就说饼图、要蓝色系就说蓝色系、"
    "指定了标题就把标题给出去）—— 这些是他的要求，你漏了就是丢需求。"
    "但**不要自己加码**：用户没提的纵轴范围、配色方案、要不要标数值、底部加不加脚注，"
    "一律别写。你看不到它的 Skill 支持哪些参数，自己发明的要求十有八九它做不到，"
    "而它为了满足你会去改 Skill 脚本、另写生成器，绕上几分钟最后超时 ——"
    "**一句你自己加的要求，就够让整个任务失败**。"
    "拿不准某个细节该不该写，就问自己：用户说过这个吗？没说过就交给它的说明书。"
)


def _referenced_artifact_ids(past: Sequence[Message]) -> frozenset[UUID]:
    """历史里被用户拖进来过的产物 id —— fetch 工具的取值范围要算上它们（决策 25）。

    这些文件属于**别的**对话（跨对话拖引用正是这个功能的意义），光靠
    conversation_id 那个条件够不着。少了这一格，第二轮「把上次那个 csv 换成
    折线图」会卡在「本对话没有这个文件」上，而它明明白白列在模型眼前的
    <attachments> 标注里 —— 决策 24 特意点名不要这种「看得见、取不回」。

    `past` 本来就在手上（视角化历史要用），这里不多查一次库。
    """
    return frozenset(
        b.artifact_id
        for m in past
        for b in parse_blocks(m.content)
        if isinstance(b, ArtifactRefBlock)
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


class FilesShelfMiddleware(AgentMiddleware):
    """只为摘要 offload 提供 state 里的 files 货架,不注册任何工具。"""

    state_schema = FilesystemState


def _base_middleware(model: BaseChatModel) -> list[AgentMiddleware]:
    """supervisor 与成员共用的中间件底座。

    含两样：工具护栏（超时 / 截断 / 异常兜底，见 tool_guard）+ 一次回复内部的
    压缩保险丝（run 结束即弃；跨回复的压缩归 compaction_service）。

    **护栏排第一位**：框架规则 first defined = outermost，它得在最外层才罩得住
    里面所有的工具调用。
    """
    return [
        ToolGuardMiddleware(),
        FilesShelfMiddleware(),
        SummarizationMiddleware(
            model=model,  # 摘要用应答者自己的模型
            backend=StateBackend(),
            # 绝对 token 阈值 —— fraction 依赖 model profile,兼容端点拿不到会静默永不触发。
            # **跟跨回复压缩共用同一条线**:这里原来写死 200_000,正好等于窗口本身,
            # 等于保险丝的额定值等于它要保护的那根线 —— 消息要堆到 20 万才触发,
            # 可堆到 19 万那次调用加上系统提示和工具定义早就超窗报错了,
            # 压缩逻辑永远轮不到跑
            trigger=("tokens", COMPACT_TRIGGER_TOKENS),
            keep=("messages", 20),
            trim_tokens_to_summarize=None,  # 类默认 4000 只摘尾部,显式关掉
        )
    ]


async def _member_to_subagent(
        member: WorkspaceMember,
        member_cfg: AgentConfig,
        user: User,
        fallback_model: BaseChatModel,
        mount: SkillMount | None,
        *,
        memory_section: str,
) -> tuple[CompiledSubAgent, dict[str, str]]:
    """把一个招募成员装配成 supervisor 可派活的子 agent。

    返回二元组的第二项 = 这个成员自己那批工具的中文展示名。成员调工具时，
    那些 tool 块带 subagent 戳嵌在前端 DelegateBlock 里渲染，同样是给人看的，
    所以要跟应答者自己的那份并进同一张表。

    成员没配 chat 模型时继承 supervisor 的模型（fallback_model）——
    模型只决定「用哪个 LLM」，成员的身份（prompt / tools / 知识库）仍是它自己的；
    这也是 deepagents 的默认语义（subagent 不配 model 则继承主 agent）。

    mount 是 supervisor 那个同一个实例，不是各自新建的：派活发生在同一张图、
    同一次回复里，成员产出的文件 supervisor 必须看得见（决策 12）。

    memory_section 只带工作区那一段,不带用户级:派活成员不直接跟用户说话,
    它收到的是 supervisor 写好的任务描述,用户是谁对它没有用。而工作区的约定
    它必须知道 —— 「对全区所有 agent 生效、又不写进任何一个 agent 自己」正是
    工作区记忆存在的理由。
    """
    agent = member.agent

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

    middleware: list[AgentMiddleware] = _base_middleware(model)

    # 这个成员自己挂了 skill 才给它文件工具（决策 19）。mount 是全场共用的一个，
    # 只要有任何一人挂了它就存在，所以不能拿它当判据。
    if mount is not None and mount.has_skills(member_cfg):
        middleware.append(mount.middleware)
        tools = [*tools, *mount.artifact_tools]  # 同应答者那份，跟文件工具同进同出
        system_prompt = f"{system_prompt}\n\n{mount.prompt_for(member_cfg)}"

    # 成员也能直接问用户。中断实测是一个一个来的（图撞上第一个就整体冻住，
    # 后面的工具压根没执行），所以不存在几个成员同时弹表单的情况，
    # 不必为并发另做处理
    tools = [*tools, AskHumanTool(
        asker_kind=SenderKind.MEMBER,
        asker_name=member_label(member.id, agent.name),
        asker_member_id=member.id,
    )]

    if memory_section:
        system_prompt = f"{system_prompt}\n\n{memory_section}"

    profile = await build_capability_profile(member_cfg, user)

    runnable = create_agent(
        model=model,
        tools=tools,
        system_prompt=system_prompt,
        middleware=middleware,
    )

    desc = f"{agent.name}：{agent.description}" if agent.description else agent.name
    subagent: CompiledSubAgent = {
        "name": member_key(member.id),
        "description": f"{desc}\n能力 · {profile}",
        # 只给成员兜底，不给 supervisor —— supervisor 挂了该让用户看见（走 adapter
        # 那条路），而成员挂了 supervisor 得有机会补救
        "runnable": _with_failure_fallback(runnable, agent.name),
    }
    return subagent, build_display_names(tools)


async def build_capability_profile(cfg: AgentConfig, user: User) -> str:
    """从 config 派生一行能力画像 —— 供 Supervisor 按能力路由。

    只取 内置工具 / Skill / KB / MCP 的「名字标签」，不碰工具 schema：
    路由层要的是「这成员挂了高德地图」「这成员会画图」，不是参数细节。
    画像长度随挂载项数增长，与单个 MCP 暴露多少工具无关。

    **Skill 这一档必须在**：它决定成员有没有那 7 个文件工具（决策 19），
    也就决定了它能不能跑脚本、产文件。漏掉这档，supervisor 会把画图这类活
    派给一个手无寸铁的成员，而且从画像上看不出哪里不对。
    """
    tags: list[str] = []

    builtin = [t.name for t in resolve_tools(cfg.builtin_tools)]
    if builtin:
        tags.append(f"内置[{','.join(builtin)}]")

    # 画像里不分来源：supervisor 只关心「这成员会不会画图」，
    # 不关心这项技能是随代码分发的还是用户自己传的
    skill_names = [s.name for s in resolve_builtin_skills(cfg.builtin_skills)]
    if cfg.skills:
        rows = await Skill.filter(id__in=cfg.skills, created_by=user)
        skill_names.extend(row.name for row in rows)
    if skill_names:
        tags.append(f"Skill[{','.join(skill_names)}]")

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


def responder_config(
        workspace: Workspace,
        responder: WorkspaceMember | None,
) -> AgentConfig:
    """应答者用谁的 config —— 没 @ 就是管家自带的那份,@ 了就是那个成员的 agent。

    抽出来是给预检和装配共用:**「配置从哪儿取、怎么解析」只能有一处**,
    两边各写一遍的话,预检放行了装配却报错,用户会收到一个空流。
    """
    return AgentConfig.model_validate(
        workspace.supervisor if responder is None else responder.agent.config
    )


async def validate_responder(
        workspace: Workspace,
        responder: WorkspaceMember | None,
) -> None:
    """开流之前的配置预检 —— 只管「这个应答者能不能开工」。

    存在的唯一理由是**保住 400 的语义**:SSE 一旦开始就只能发 error 事件、
    返不了 400 JSON,而「管家没配模型」这类是请求当场就该被拒的错误,
    不该变成一条半截的对话消息。

    校验规则不在这儿重写,而是**借 build_chat_model 跑一遍再把结果扔掉** ——
    模型存不存在、类型对不对的判断只能有一处。代价是每轮多一次 AIModel
    查询(约 1ms),换「预检和装配永远不会对同一份配置给出不同答案」。

    管不到成员和沙箱 —— 那些要真装配才知道,失败时走流内 error 帧。

    Raises:
        ValidationException: 未配 chat 模型 / 槽位类型错 / 模型不存在
    """
    cfg = responder_config(workspace, responder)
    if cfg.models.chat is None:
        raise ValidationException("应答者未配置 chat 模型")
    await build_chat_model(cfg.models.chat)


async def build_workspace_graph(
        workspace: Workspace,
        request: ChatStreamRequest,
        user: User,
        past: list[Message],  # ← 新增:DB 历史消息(视角化用)
        responder: WorkspaceMember | None = None,  # None = supervisor;否则 = 被 @ 的成员
        *,
        message_id: UUID,
        conversation_id: UUID,
        attachments: Sequence[SandboxArtifact],
) -> PreparedStream:
    """装配 workspace 对话图 —— 内置 supervisor 套外层 StateGraph。

        与 prepare_stream 同形态返回 PreparedStream，供 run_chat_stream 直接消费。
        所有可能 raise 的逻辑在此完成 —— FastAPI handler 接 ValidationException → 400 JSON，
        此刻 SSE 还没起。

        Args:
            workspace: 已取出的 Workspace 实例(supervisor jsonb 在 workspace.supervisor)
            request:   当前轮 user 输入 + 历史(历史由 stream 端点从 DB 拼好)
            user:      当前用户(KB 工具归属校验用)
            past:      DB 历史消息(视角化用)
            responder: None = supervisor;否则 = 被 @ 的成员
            message_id: 本轮 assistant 消息 ID —— 交付区目录名与产物归组键
            conversation_id: 产物落库时挂在哪个对话下
            attachments: 用户拖进输入框的历史产物（决策 25），已由 stream 端点
                查库校过归属。**刻意不给默认值** —— 同 conversation_id，漏传的话
                签名对、类型对、不报错，只是用户附的文件静默消失

        Raises:
            ValidationException: supervisor 未配 chat 模型 / 槽位类型错 / 模型不存在
    """

    # 拉本 workspace 招募的成员（select_related agent —— 正向 FK 走 JOIN，一次查询）
    members = await WorkspaceMember.filter(
        workspace_id=workspace.id
    ).select_related("agent")

    member_names = {m.id: m.agent.name for m in members}
    # 花名册 / 自我身份用唯一标签(名字#id8),与 <msg from> 标签、行动痕迹三头同源
    member_roster = [member_label(m.id, m.agent.name) for m in members]

    # 根据 responder 定三件事:用谁的 config、什么视角、能不能派活
    cfg = responder_config(workspace, responder)

    if responder is None:
        viewer = Viewer(sender_kind=SenderKind.SUPERVISOR)
        can_delegate = True
        self_name = SPEAKER_SUPERVISOR  # 与 assembler 打的 from 标签同源
        self_alias = SPEAKER_SUPERVISOR
    else:
        viewer = Viewer(sender_kind=SenderKind.MEMBER, member_id=responder.id)
        can_delegate = False  # @直连成员不派活
        self_name = member_label(responder.id, responder.agent.name)  # 与 from 标签同源
        self_alias = responder.agent.name  # 用户 @ 时用的裸名

    if cfg.models.chat is None:
        raise ValidationException("应答者未配置 chat 模型")

    chat_model = await build_chat_model(cfg.models.chat)
    tools = await assemble_tools(cfg, user)

    # 视角化历史（viewer 跟着应答者走）。**刻意提到装配前面拼**：它会告诉我们
    # 历史里有没有工具结果被截断，而那决定了要不要给应答者配取回工具
    context = await ViewContextAssembler().build(
        past, viewer, member_names, await group_by_message(conversation_id),
        await latest_summary(conversation_id),
    )
    if context.truncated:
        # 只在真有截断标记时才挂：挂了没标记 = 白占工具位、还可能诱导瞎调；
        # 有标记没挂 = 给模型指了条死路。两者同源才不会跑偏。
        # 派活成员不需要它 —— 它们只收到一段任务描述，根本看不见历史
        tools = [*tools, ToolResultFetchTool(conversation_id=conversation_id)]

    # 常驻记忆:一次取两个尺度。挂在(user, workspace)上,按**当前登录用户**取,
    # 不按 workspace.created_by —— 今天二者相同,工作区哪天能共享时前者才是对的
    memory: MemorySnapshot = await MemoryService().snapshot(
        user_id=user.id, workspace_id=workspace.id
    )

    # 写记忆只有 supervisor 一个入口 —— @直连成员这一轮虽然也是应答者、也读记忆,
    # 但不给它写:写入要的是全局视角,而它只看得见自己被 @ 的这一段
    if responder is None:
        tools = [*tools, MemoryUpdateTool(user_id=user.id, workspace_id=workspace.id)]

    # 派活成员的 config 先 parse 出来：既要参与 skill 并集，又要传给 _member_to_subagent，
    # 免得同一份 jsonb 解两遍。@直连时不派活，场上只有应答者自己。
    member_cfgs: list[tuple[WorkspaceMember, AgentConfig]] = (
        [(m, AgentConfig.model_validate(m.agent.config)) for m in members]
        if can_delegate else []
    )

    # skill 沙箱：一轮回复共用一个（决策 12）。这一刀先只装应答者自己的，
    # 派活成员的下一刀并进来。scope_id 用 workspace.id —— 工作区跨对话保留。
    mount = await build_skill_mount(
        [cfg, *(c for _, c in member_cfgs)],
        user,
        scope_id=workspace.id,
        message_id=message_id,
        conversation_id=conversation_id,
        referenced_artifact_ids=_referenced_artifact_ids(past),
    )

    # 用户拖进来的附件（决策 25）：有沙箱就把字节灌进工作区，没有就如实说明。
    # **没沙箱不报错** —— 「附件只能给沙箱用」是这一刀的现状、不是永久前提，
    # 以后 PDF / 图片进模型视野那一刀落地时，同一个块自然多一条去处
    attachments_note = ""
    if attachments:
        attachments_note = (
            await inject_attachments(mount.backend, mount.paths, attachments)
            if mount is not None
            else describe_unavailable(attachments)
        )

    # base 框架(协议说明 + 名单 + 日期 + 应答者自我身份)+ 应答者自己的人设
    base = _workspace_base_prompt(workspace.name, member_roster, self_name, self_alias)

    system_prompt = f"{base}\n{cfg.system_prompt}" if cfg.system_prompt else base

    # 派活 middleware 只有 supervisor 挂
    middleware: list[AgentMiddleware] = [
        WorkspaceContextMiddleware(),
        *_base_middleware(chat_model),
    ]

    # 应答者自己挂了 skill 才给文件工具 —— 同 _member_to_subagent 的判据
    if mount is not None and mount.has_skills(cfg):
        middleware.append(mount.middleware)
        # 取回历史产物的工具跟那 7 个同进同出：看得见 <artifacts> 却取不回来没有意义
        tools = [*tools, *mount.artifact_tools]
        system_prompt = f"{system_prompt}\n\n{mount.prompt_for(cfg)}"

    # 问用户的工具。asker 用上面算好的应答者身份绑死，模型改不了自己是谁 ——
    # 前端据此显示「张三在问你」而不是笼统的「AI 在问你」
    tools = [*tools, AskHumanTool(
        asker_kind=SenderKind.SUPERVISOR if responder is None else SenderKind.MEMBER,
        asker_name=self_name,
        asker_member_id=None if responder is None else responder.id,
    )]

    # 工具展示名：应答者自己的先收着（此时 tools 已追加完取回工具 / 文件工具、
    # 彻底定型），派活成员的在下面并进来
    display_names = build_display_names(tools)

    if can_delegate:
        built = [
            await _member_to_subagent(
                member, member_cfg, user, chat_model, mount,
                # 只给工作区那段 —— 派活成员不直接面对用户
                memory_section=_memory_section(
                    about_user="", about_workspace=memory.workspace_scope
                ),
            )
            for member, member_cfg in member_cfgs
        ]
        subagents = [subagent for subagent, _ in built]
        for _, member_display_names in built:
            display_names.update(member_display_names)
        if subagents:
            middleware.append(
                SubAgentMiddleware(backend=StateBackend(), subagents=subagents)
            )
        # supervisor 自己未必挂 skill，也就拿不到那段 skill prompt（决策 19），
        # 于是它不知道「skill 的成果是写进交付区的文件」，派活时会凭常识要求
        # 「把代码返回给我」—— 成员照做，成果就落进对话正文，产物表一行都没有。
        # 只在场上真有人带 skill 时才补这段，否则是废话
        if mount is not None and any(mount.has_skills(c) for _, c in member_cfgs):
            system_prompt = f"{system_prompt}\n\n{_DELEGATE_SKILL_NOTE}"

    # 记忆垫在整段 system prompt 的最后一节(见 _memory_section 的说明)。
    # 应答者两段都给:supervisor 和被 @ 直连的成员,这一轮都在直接跟用户说话
    responder_memory = _memory_section(
        about_user=memory.user_scope, about_workspace=memory.workspace_scope
    )
    if responder_memory:
        system_prompt = f"{system_prompt}\n\n{responder_memory}"

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
    # 只挂外层：内层 responder_agent 作为节点嵌进来，跟着外层的存档走。
    # 两层都挂会写两份
    graph = builder.compile(checkpointer=get_checkpointer())

    # 这次回复的 user 输入 = 正文 + 附件标注。不走 to_lc_messages 是因为那是通用摊平
    # （history + current 一起翻），这里只要当前一句、还得在尾巴上接一行标注
    current = "\n".join(
        part for part in (content_to_text(request.content), attachments_note) if part
    )
    # 视角化历史（上面已拼好）+ 当前这句
    messages = [*context.messages, HumanMessage(current)]

    # 收产物的回调：挂了 skill 才有交付区。产物绑 conversation —— workspace 那条路
    # 的消息入库，卡片将来靠这个字段按对话捞回来
    collect: ArtifactCollector | None = None
    close: SandboxCloser | None = None
    if mount is not None:
        collect = partial(
            collect_artifacts,
            mount.backend,
            mount.paths,
            user=user,
            scope_id=workspace.id,
            message_id=message_id,
            conversation_id=conversation_id,
        )
        close = mount.close

    return PreparedStream(
        graph=graph, messages=messages, collect=collect, close=close,
        display_names=display_names,
    )
