"""LangChain chat model 工厂 —— ModelSlot → BaseChatModel。

为什么函数形态而非静态实例：
- 每次请求重建凭证 / 配置（防 Provider 改 base_url / key 后实例不刷新）
- Workspace 跨节点换模型场景（Supervisor 用 A、NPC 各用各的）天然支持
- BaseChatModel 本身就是廉价对象，重建无性能负担

凭证解析：Model 级覆盖优先、空则 fallback Provider 级（沿用 ModelClient 同款）。
"""

import asyncio
import logging
from collections.abc import AsyncIterator, Callable
from typing import Any
from uuid import UUID
from collections.abc import Awaitable
from dataclasses import dataclass, field
from functools import partial

from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain.agents.middleware import AgentMiddleware
from langchain_core.tools import BaseTool
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command
from uuid_utils import compat as uuid_compat

from app.models.sandbox import SandboxArtifact
from app.services.sandbox.artifact import collect_artifacts
from app.agents.runtime.adapter import adapt_chat_stream
from app.agents.runtime.chat_models import ReasoningChatOpenAI, apply_reasoning_params
from app.agents.runtime.events import EventType, sse_event
from app.agents.runtime.param_adapter import get_param_adapter
from app.agents.runtime.spec import AgentSpec
from app.agents.runtime.tool_guard import ToolGuardMiddleware
from app.agents.templates import get_template
from app.core.exceptions import ValidationException
from app.core.identifiers import short_id
from app.core.observability import TraceContext, get_langfuse_handler
from app.models import KnowledgeBase, MCPServer, User
from app.models.model import AIModel
from app.schemas.agent.chat_schema import ChatStreamRequest
from app.schemas.agent.chat_schema import (
    ArtifactRefBlock,
    ContentBlock,
    HistoryMessage,
    TextBlock,
)
from app.schemas.agent.config_schema import AgentConfig
from app.schemas.agent.config_schema import ModelSlot
from app.services.mcp.mcp_runtime import fetch_tools_for_server
from app.services.model.model_client import ModelClient
from app.services.skill.mount import build_skill_mount
from app.tools import resolve_tools
from app.tools.knowledge_retrieval import KnowledgeRetrievalTool

logger = logging.getLogger(__name__)

# 一次回复内的最大步数（LangGraph 术语叫 super-step：模型说一次话算一步，
# 跑一次工具算一步）。不设则吃 LangGraph 默认的 25 —— 那是框架默认值，不是
# 我们的决定。
#
# 取 40 而非 25：workspace 比单 agent 深。supervisor 每派一个活就是「模型决定
# 派谁 + 跑 task 工具」两步，派 10 个成员吃掉 20 步，加上开场和收尾，25 刚好卡
# 在边缘。**卡边缘的坏处是撞线的会变成「正常但复杂的任务」而不是真死循环。**
# 40 给复杂任务留余量，同时离失控还很远：真转起圈来 40 步照样兜得住。
#
# 对照：Dify 默认 10（可配到 99）、Letta 50、LangGraph 默认 25。
RECURSION_LIMIT = 40

# provider_type → LangChain model_provider
# OpenAI 兼容 provider 全走 "openai"（靠 base_url 区分上游），只有 Anthropic 走官方协议。
# 未知类型 fallback "openai" —— 最宽容 + log warning。

# sink：事件旁路回调 —— runner 每产一个事件，先喂 sink 一份再序列化成 SSE。
SinkFn = Callable[[EventType, dict[str, Any]], None]

# 收产物的回调：参数已在 prepare_stream 里绑好，调用方只管 await 一下
ArtifactCollector = Callable[[], Awaitable[list[SandboxArtifact]]]

# 一轮结束的收尾：docker driver 销毁容器，local driver 是空操作
SandboxCloser = Callable[[], Awaitable[None]]

# 本轮 token 用量汇总：终止帧捎一份给前端，与落库的三个字段同源同形。
# 传的是「取数的动作」而非数本身 —— 调用 run_chat_stream 那一刻桶还是空的，
# 得等流跑完 runner 自己去兑现。
UsageSummarizer = Callable[[], dict[str, Any]]

# SSE message_start 的 role —— 流式产出的消息恒为 assistant（协议固定值）
_SSE_ROLE_ASSISTANT = "assistant"


@dataclass(frozen=True, slots=True)
class PreparedStream:
    """SSE 流开起来前装配好的一切。

    刻意用 dataclass 而非元组：workspace 接线时还要把 mount 带出来
    （supervisor 与各成员共用同一个），元组会一路膨胀成四元、五元。
    """

    graph: CompiledStateGraph
    messages: list[BaseMessage]
    collect: ArtifactCollector | None  # 没挂 skill 就没有交付区，恒为 None
    close: SandboxCloser | None  # 同上；docker driver 靠它销毁容器
    # 工具 name → 中文展示名。纯展示用，LLM 侧一点不参与（它认的仍是 name）。
    # 给默认值是为了不破坏任何构造点：将来第三条路忘了传，退化成现状而非报错
    display_names: dict[str, str] = field(default_factory=dict)


def _feed_sink(sink: SinkFn | None, event: EventType, payload: dict[str, Any]) -> None:
    """把事件喂给 sink（装了才喂）。sink 自己炸了只 log —— 旁路故障不打断主流。"""
    if sink is None:
        return
    try:
        sink(event, payload)
    except Exception:
        logger.exception("stream sink failed on %s; stream continues", event)


_PROVIDER_TYPE_TO_LC: dict[str, str] = {
    "openai": "openai",
    "deepseek": "openai",
    "dashscope": "openai",
    "siliconflow": "openai",
    "custom": "openai",
    "anthropic": "anthropic",
}

# OpenAI 兼容家族 —— DeepSeek / 通义 / SiliconFlow / custom 全归这一格，
# 它们共用 ChatOpenAI 走同一套协议，故推理内容的缺口也一处补齐。
_LC_PROVIDER_OPENAI = "openai"

_DEFAULT_LC_PROVIDER = _LC_PROVIDER_OPENAI

# AIModel.model_type 期望值（防 stt / tts 模型误塞 chat 槽位）
_EXPECTED_MODEL_TYPE_CHAT = "chat"


def _resolve_lc_provider(provider_type: str) -> str:
    """provider_type → LangChain model_provider。未知类型 fallback 并告警。"""
    lc_provider = _PROVIDER_TYPE_TO_LC.get(provider_type)
    if lc_provider is None:
        logger.warning(
            "unknown provider_type=%r, fallback to %r",
            provider_type, _DEFAULT_LC_PROVIDER,
        )
        return _DEFAULT_LC_PROVIDER
    return lc_provider


async def build_chat_model(slot: ModelSlot) -> BaseChatModel:
    """从 ModelSlot 构造 LangChain chat 模型。

        Args:
            slot: AgentConfig.models.chat（已校验非 None）

        Returns:
            BaseChatModel —— init_chat_model 的产物，可直接 .astream_events 跑

        Raises:
            ValidationException: 模型不存在 / 类型不是 chat
    """

    ai_model = (
        await AIModel.filter(id=slot.id)
        .prefetch_related("provider")
        .first()
    )
    if ai_model is None:
        raise ValidationException(f"AIModel 不存在：{slot.id}")
    if ai_model.model_type != _EXPECTED_MODEL_TYPE_CHAT:
        raise ValidationException(
            f"chat 槽位不能配 {ai_model.model_type} 类型的模型"
        )

    # 凭证：Model 级覆盖优先，空则 fallback Provider 级
    provider = ai_model.provider
    base_url, creds = ModelClient.resolve_credentials(ai_model)
    api_key = creds.api_key

    lc_provider = _resolve_lc_provider(provider.provider_type)

    # params：exclude_none —— 没填的让 provider 用自己默认
    # 顺序有讲究：先翻思考档位（会往 extra_body 写），再走 provider 家族适配
    # （它也往 extra_body 写 max_tokens，靠 setdefault 合并而非互相覆盖）
    params = slot.params.model_dump(exclude_none=True)
    params = apply_reasoning_params(params)
    init_kwargs = get_param_adapter(lc_provider).to_init_kwargs(params)

    # 空 Key：占位符过 SDK 构造校验，再把真正发出的 Authorization 覆盖成空，
    # 等价于"不带/带空鉴权"请求上游（无鉴权服务用）。
    if not api_key:
        headers = {**init_kwargs.get("default_headers", {}), "Authorization": ""}
        init_kwargs["default_headers"] = headers
        api_key = "placeholder"

    # openai 家族绕开 init_chat_model 工厂 —— 它按 model_provider 固定选中
    # ChatOpenAI，而我们要的是补了推理内容的子类。anthropic 等其余家族
    # 没有这个缺口，继续走工厂。
    if lc_provider == _LC_PROVIDER_OPENAI:
        return ReasoningChatOpenAI(
            model=ai_model.model_name,
            base_url=base_url,
            api_key=api_key,
            **init_kwargs,
        )

    return init_chat_model(
        model=ai_model.model_name,
        model_provider=lc_provider,
        base_url=base_url,
        api_key=api_key,
        **init_kwargs
    )


def content_to_text(blocks: list[ContentBlock]) -> str:
    """ContentBlock 数组拼成 str —— **只取文本块**。

    非文本块（artifact_ref 等）一律跳过：它们是结构，不是话。该让模型知道的事
    由各自的渲染层拼成标注另行追加（workspace 那行 <attachments> 就是），
    不在这里含糊地替它拼一句人话 —— 拼了就会跟真正的渲染层说重。

    去掉下划线转公开：workspace 那条路要自己拼当前轮消息，正文归这个函数、
    附件标注归它接在后面。
    """
    return "".join(b.text for b in blocks if isinstance(b, TextBlock))


def to_lc_messages(
        history: list[HistoryMessage],
        current: list[ContentBlock],
) -> list[BaseMessage]:
    """ChatStreamRequest 的 history + 当前轮 content → LangChain messages。

    system_prompt 由 template.build(system_prompt=...) 经 create_agent
    注入、不入 messages，避免后续 graph 节点重复感知（deepagents 反例）。
    """
    msgs: list[BaseMessage] = []

    for h in history:
        text = content_to_text(h.content)
        if h.role == "user":
            msgs.append(HumanMessage(text))
        else:  # assistant
            msgs.append(AIMessage(text))

    msgs.append(HumanMessage(content_to_text(current)))
    return msgs


async def assemble_tools(cfg: AgentConfig, user: User) -> list[BaseTool]:
    """聚合 agent 各来源工具 → list[BaseTool]，喂给 template.build。

    装配点：prepare_stream 只认这一个入口，新增来源（MCP / custom）在此扩、
    不动调用方。async 为未来 MCP/custom 的 IO 加载预留。

    来源：
    - builtin：registry 单例（无状态）
    - knowledge：per-KB bound 实例（运行时按 cfg.knowledge 实例化）
    - mcp：按 cfg.mcp_servers 连 server 拉工具（并发 + 单 server 失败容错跳过）
    """
    tools: list[BaseTool] = []
    tools.extend(resolve_tools(cfg.builtin_tools))

    if cfg.knowledge:
        # 一次性 prefetch 所有挂载的 KB；filter created_by 顺便归属校验，
        # 用户配错 / KB 已删的 id 自动被过滤（容错，不让残留配置炸整个 agent）
        kbs = await KnowledgeBase.filter(
            id__in=cfg.knowledge,
            created_by=user
        ).prefetch_related("rerank_model").all()

        for kb in kbs:
            # 精排模型被禁用时静默降级回单级检索：KB 上的是「默认值」，默认值失效
            # 不该让整个库检索失灵（同 MCP 分支「禁用 id 自动过滤」的规矩）；
            # 命中测试那条路显式传模型 id，仍然硬报错——那是用户的明确指令
            rerank_model = kb.rerank_model

            tools.append(
                KnowledgeRetrievalTool(
                    # 取后 8 位而非前 8 位：UUIDv7 前面是毫秒时间戳，同一分钟建的
                    # 两个库前 8 位一样 —— 同时挂给一个 agent 就是两个重名工具
                    name=f"knowledge_{short_id(kb.id)}",
                    description=_build_kb_tool_description(kb),
                    display_name=f"知识库《{kb.name}》",
                    kb_id=kb.id,
                    user=user,
                    default_mode=kb.retrieval_mode,
                    default_rerank_model_id=(
                        rerank_model.id if rerank_model and rerank_model.is_enabled else None
                    ),
                )
            )

    if cfg.mcp_servers:
        # 拉挂载的、属于本人的、启用中的 server；残留 / 禁用 id 自动过滤
        servers = await MCPServer.filter(
            id__in=cfg.mcp_servers, created_by=user, enabled=True
        ).all()
        # 并发连接拉工具；单个 server 失败容错跳过，不连累整个装配
        results = await asyncio.gather(
            *(fetch_tools_for_server(s) for s in servers),
            return_exceptions=True,
        )
        for server, result in zip(servers, results):
            if isinstance(result, Exception):
                logger.warning(
                    "MCP server 工具装配失败 name=%s: %s", server.name, result
                )
                continue
            tools.extend(result)

    return tools


def build_display_names(tools: list[BaseTool]) -> dict[str, str]:
    """工具 name → 中文展示名，供 adapter 盖进 tool_use 事件给前端显示。

    只有 CoCoTool 定义了 display_name；MCP 拉回来的是原生 LangChain 工具，
    getattr 取不到就不进表 —— 前端那边自然回落显示原始 name。

    与 assemble_tools 分开而不是让它返二元组：调用方有三处（playground /
    workspace 应答者 / workspace 成员），后两处都要在 tools 追加过
    ToolResultFetchTool、artifact_tools 之后才算，时机与装配点对不齐。
    """
    names: dict[str, str] = {}
    for tool in tools:
        display_name = getattr(tool, "display_name", None)
        if display_name:
            names[tool.name] = display_name
    return names


def _build_kb_tool_description(kb: KnowledgeBase) -> str:
    """KB tool description —— LLM 选库就靠它。

    塞 KB 的人类语义（name + 用户填的 description），让 LLM 在多 KB
    场景下按主题正确路由。
    """
    desc = kb.description or "（暂无描述）"
    return (
        f"检索知识库《{kb.name}》：{desc}。"
        f"当你需要查询与此主题相关的信息时使用，输入一个自然语言查询。"
    )


async def prepare_stream(
        spec: AgentSpec,
        request: ChatStreamRequest,
        user: User,
        *,
        message_id: UUID,
) -> PreparedStream:
    """SSE 流开起来前的同步装配 —— 配置校验 / 取模板 / 装 chat model / 装 graph。

    所有可能 raise 的逻辑在此完成 —— FastAPI handler 接 ValidationException → 400 JSON。
    一旦返回 (graph, messages)，调用方就可以放心交给 StreamingResponse（不再有 raise 风险）。

    Raises:
        ValidationException: 模板不在册 / chat 模型未配 / 槽位类型错
    """
    # 决策 26：Playground 不接拖引用 —— 它的消息不入库、产物的 conversation_id 为
    # NULL，「本对话」在那边根本不存在。与其编一个近似答案，不如当场说不支持
    if any(isinstance(b, ArtifactRefBlock) for b in request.content):
        raise ValidationException("Playground 不支持引用历史产物，请在工作空间里使用")

    cfg = spec.config

    if cfg.models.chat is None:
        raise ValidationException("Agent 未配置 chat 模型")

    template = get_template(spec.template)
    if template is None:
        raise ValidationException(f"模板不在册：{spec.template}")

    chat_model = await build_chat_model(cfg.models.chat)

    # Playground 只有一个 agent 在场，包成单元素列表；workspace 那条路传一串
    # conversation_id=None：Playground 的消息不入库、产物没有对话归属，
    # 「本对话」在那边不存在，故不给取回工具（决策 26）
    mount = await build_skill_mount(
        [cfg], user, scope_id=user.id, message_id=message_id,
        conversation_id=None,
        referenced_artifact_ids=frozenset(),  # 没有对话就没有历史，自然无从引用
    )
    system_prompt = cfg.system_prompt
    # 护栏排第一位 —— 框架规则 first defined = outermost，它得在最外层才罩得住
    # 里面所有的工具调用（workspace 那条路由 _base_middleware 挂同一个）
    middleware: list[AgentMiddleware] = [ToolGuardMiddleware()]

    collect: ArtifactCollector | None = None
    close: SandboxCloser | None = None

    if mount is not None:
        middleware.append(mount.middleware)
        # Playground 的产物不挂对话（消息本身就不入库），conversation_id 留空
        collect = partial(
            collect_artifacts,
            mount.backend,
            mount.paths,
            user=user,
            scope_id=user.id,
            message_id=message_id,
        )
        close = mount.close

        # skill 清单拼在实例人设之后：先是「你是谁」，再是「你有哪些工具书」
        skills_prompt = mount.prompt_for(cfg)
        system_prompt = (
            f"{system_prompt}\n\n{skills_prompt}" if system_prompt else skills_prompt
        )

    # 提成变量而非内联进 build()：下面算展示名要用同一份
    tools = await assemble_tools(cfg, user)

    graph = template.build(
        chat_model=chat_model,
        system_prompt=system_prompt,
        tools=tools,
        middleware=middleware,
    )

    messages = to_lc_messages(request.history, request.content)
    return PreparedStream(
        graph=graph, messages=messages, collect=collect, close=close,
        display_names=build_display_names(tools),
    )


async def run_chat_stream(
        graph: CompiledStateGraph,
        graph_input: list[BaseMessage] | Command,
        *,
        message_id: UUID,
        collect: ArtifactCollector | None = None,
        close: SandboxCloser | None = None,
        usage: UsageSummarizer | None = None,
        sink: SinkFn | None = None,
        trace: TraceContext | None = None,
        display_names: dict[str, str] | None = None,
) -> AsyncIterator[str]:
    """SSE 流主编排 —— 包 message_start / 驱动 adapter / 兜底 message_stop。

    graph_input：消息列表 = 新开一轮对话；Command = 用户填完表单后从存档继续。
    后者**不带历史** —— 存档里已有完整的执行现场，再拼一遍就是同一段对话
    进两次。

    sink：可选事件旁路。每个事件在粘成 SSE 字符串之前，原样 (EventType, payload)
    先喂 sink 一份 —— 一份流前端、一份进桶（Unix tee 分叉）。Playground 不传、
    行为不变；workspace 传 collector.feed 攒流式内容落库。

    异常分层：
    - 配置 / 模板 / 模型校验 → prepare_stream raise → FastAPI 400 JSON（SSE 还没起）
    - LLM 调用 / adapter 内部 → adapter 全部 try/except 翻成 error 帧（脱敏 + 关块）
    - sink 内部 → _feed_sink 兜住只 log（旁路故障不打断对话主流）
    - message_stop → finally 兜底必发（前端靠它关活气泡，光标不卡）
    """

    start_payload = {"id": str(message_id), "role": _SSE_ROLE_ASSISTANT}
    _feed_sink(sink, EventType.MESSAGE_START, start_payload)
    yield sse_event(EventType.MESSAGE_START, start_payload)

    # 本轮是否卡在人工确认上。必须在 try 之前定义 —— finally 里要读它，
    # 而 try 内部任何一步抛异常都可能让 try 里的赋值来不及执行
    interrupted = False

    try:
        # Langfuse:配了 key 才挂 callback;trace 归因走 config.metadata(langfuse_* 键)
        handler = get_langfuse_handler()
        # 步数上限。deepagents 的 task 工具里写明：父的 recursion_limit 会经
        # langgraph 的 ensure_config 自动传给子 agent（子 agent 自绑的优先），
        # 所以设这一处就同时罩住 supervisor 和它派活的每个成员 —— 各自一份
        # 预算，不是全家共享。
        # thread_id = 本轮 assistant 消息 ID —— 一次回复一个存档槽。
        # 不用 conversation_id：历史由业务侧按应答者视角另拼，若按对话粒度复用
        # 同一个槽，add_messages 的追加语义会把上一轮的视角历史叠进来。
        # Playground 的图没挂 checkpointer，传了会被安全忽略（已实测）
        config: dict[str, Any] = {
            "recursion_limit": RECURSION_LIMIT,
            "configurable": {"thread_id": str(message_id)},
        }

        if handler is not None:
            config["callbacks"] = [handler]
            if trace is not None:
                if trace.name:
                    config["run_name"] = trace.name
                config["metadata"] = trace.to_config_metadata()

        events = graph.astream_events(
            # 两种输入形态：消息列表 = 新开一轮；Command = 从存档接着跑。
            # astream_events 本来就两种都吃，这里只原样转手、不替它判断
            {"messages": graph_input} if isinstance(graph_input, list) else graph_input,
            version="v2",
            # 不再写 `config or None`：加了 recursion_limit 之后这个字典永远
            # 非空，那个兜底分支已经不可能触发
            config=config,
        )

        async for event, payload in adapt_chat_stream(events, display_names):
            if event == EventType.INTERRUPT:
                interrupted = True
            _feed_sink(sink, event, payload)
            yield sse_event(event, payload)

    finally:
        # 暂停不是收尾：卡在表单上时这轮还没跑完。此时收产物会重复收（等用户
        # 填完、「继续」那条流跑到底时还要再收一次），销毁容器更会把 Agent 做
        # 到一半的东西连锅端掉 —— 用户填完答案接着跑时工作区得还在。
        # 容器就这么开着等人的风险由 sandboxd 的反收割兜（用户不填就走超时）
        # 产物帧必须赶在 message_stop 之前 —— 前端收到 stop 就把这条消息收口了
        if collect is not None and not interrupted:
            try:
                artifacts = await collect()
                if artifacts:
                    payload = {
                        "message_id": str(message_id),
                        "artifacts": [
                            {
                                "id": str(a.id),
                                "filename": a.filename,
                                "size": a.size,
                                "content_type": a.content_type,
                            }
                            for a in artifacts
                        ],
                    }
                    _feed_sink(sink, EventType.ARTIFACTS, payload)
                    yield sse_event(EventType.ARTIFACTS, payload)
            except Exception:
                # 收产物失败不连累这轮回复：前端少一组卡片，消息照常收尾。
                # CancelledError 继承 BaseException、不会被这里接住 —— 用户掐断时
                # 产物就不收了（文件留在交付区），这是定好的行为，不是漏网。
                logger.exception("产物回收失败，跳过产物帧 message_id=%s", message_id)

        # 销毁容器**必须排在收产物之后**：产物就躺在容器里，先销毁就什么都没了。
        # 它也不是唯一保障 —— 用户掐断时抛的是 CancelledError（继承 BaseException），
        # 这里接不住、这段根本执行不到，那种情况由 sandboxd 的反收割兜底。
        if close is not None and not interrupted:
            try:
                await close()
            except Exception:
                logger.exception("沙箱收尾失败 message_id=%s，等反收割兜底", message_id)


        # generator finally 兜底：自身 yield 也包 try，二次失败只 log 不再 raise
        try:
            stop_payload: dict[str, Any] = {"id": str(message_id)}
            if interrupted:
                # 前端据此知道「别收气泡，下面要渲染表单」。正常结束时不带这个
                # 字段 —— 对不认识它的旧前端向后兼容
                stop_payload["reason"] = "interrupted"
            if usage is not None:
                try:
                    stop_payload |= usage()
                except Exception:
                    # 汇总失败不连累收尾：前端少个数字，活气泡照常关
                    logger.exception("token 用量汇总失败，message_stop 照发 id=%s", message_id)
            _feed_sink(sink, EventType.MESSAGE_STOP, stop_payload)
            yield sse_event(EventType.MESSAGE_STOP, stop_payload)

        except Exception:
            logger.exception("emit message_stop failed")
