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
from dataclasses import dataclass
from functools import partial

from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain.agents.middleware import AgentMiddleware
from langchain_core.tools import BaseTool
from langgraph.graph.state import CompiledStateGraph
from uuid_utils import compat as uuid_compat

from app.models.sandbox import SandboxArtifact
from app.services.sandbox.artifact import collect_artifacts
from app.agents.runtime.adapter import adapt_chat_stream
from app.agents.runtime.events import EventType, sse_event
from app.agents.runtime.param_adapter import get_param_adapter
from app.agents.runtime.spec import AgentSpec
from app.agents.templates import get_template
from app.core.exceptions import ValidationException
from app.core.observability import TraceContext, get_langfuse_handler
from app.models import KnowledgeBase, MCPServer, User
from app.models.model import AIModel
from app.schemas.agent.chat_schema import ChatStreamRequest
from app.schemas.agent.chat_schema import ContentBlock, HistoryMessage
from app.schemas.agent.config_schema import AgentConfig
from app.schemas.agent.config_schema import ModelSlot
from app.services.mcp.mcp_runtime import fetch_tools_for_server
from app.services.model.model_client import ModelClient
from app.services.skill.mount import build_skill_mount
from app.tools import resolve_tools
from app.tools.knowledge_retrieval import KnowledgeRetrievalTool

logger = logging.getLogger(__name__)

# provider_type → LangChain model_provider
# OpenAI 兼容 provider 全走 "openai"（靠 base_url 区分上游），只有 Anthropic 走官方协议。
# 未知类型 fallback "openai" —— 最宽容 + log warning。

# sink：事件旁路回调 —— runner 每产一个事件，先喂 sink 一份再序列化成 SSE。
SinkFn = Callable[[EventType, dict[str, Any]], None]

# 收产物的回调：参数已在 prepare_stream 里绑好，调用方只管 await 一下
ArtifactCollector = Callable[[], Awaitable[list[SandboxArtifact]]]

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

_DEFAULT_LC_PROVIDER = "openai"

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

    # params：exclude_none —— 没填的让 provider 用自己默认；再按 provider 家族方言翻译入参
    params = slot.params.model_dump(exclude_none=True)
    init_kwargs = get_param_adapter(lc_provider).to_init_kwargs(params)

    # 空 Key：占位符过 SDK 构造校验，再把真正发出的 Authorization 覆盖成空，
    # 等价于"不带/带空鉴权"请求上游（无鉴权服务用）。
    if not api_key:
        headers = {**init_kwargs.get("default_headers", {}), "Authorization": ""}
        init_kwargs["default_headers"] = headers
        api_key = "placeholder"

    return init_chat_model(
        model=ai_model.model_name,
        model_provider=lc_provider,
        base_url=base_url,
        api_key=api_key,
        **init_kwargs
    )


def _content_to_text(blocks: list[ContentBlock]) -> str:
    """ContentBlock 数组拼成 str。

    P0 union 只有 TextBlock，直接拼 `text` 字段。P1 加 ToolUseBlock /
    ImageBlock 时这里扩 multi-modal 块（HumanMessage 支持 list-of-content
    multi-modal 形态）。
    """
    return "".join(b.text for b in blocks)


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
        text = _content_to_text(h.content)
        if h.role == "user":
            msgs.append(HumanMessage(text))
        else:  # assistant
            msgs.append(AIMessage(text))

    msgs.append(HumanMessage(_content_to_text(current)))
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
                    name=f"knowledge_{kb.id.hex[:8]}",
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
    cfg = spec.config

    if cfg.models.chat is None:
        raise ValidationException("Agent 未配置 chat 模型")

    template = get_template(spec.template)
    if template is None:
        raise ValidationException(f"模板不在册：{spec.template}")

    chat_model = await build_chat_model(cfg.models.chat)

    # Playground 只有一个 agent 在场，包成单元素列表；workspace 那条路传一串
    mount = await build_skill_mount([cfg], user, scope_id=user.id, message_id=message_id)
    system_prompt = cfg.system_prompt
    middleware: list[AgentMiddleware] = []

    collect: ArtifactCollector | None = None

    if mount is not None:
        middleware.append(mount.middleware)
        # Playground 的产物不挂对话（消息本身就不入库），conversation_id 留空
        collect = partial(
            collect_artifacts,
            mount.paths,
            user=user,
            scope_id=user.id,
            message_id=message_id,
        )

        # skill 清单拼在实例人设之后：先是「你是谁」，再是「你有哪些工具书」
        skills_prompt = mount.prompt_for(cfg)
        system_prompt = (
            f"{system_prompt}\n\n{skills_prompt}" if system_prompt else skills_prompt
        )

    graph = template.build(
        chat_model=chat_model,
        system_prompt=system_prompt,
        tools=await assemble_tools(cfg, user),
        middleware=middleware,
    )

    messages = to_lc_messages(request.history, request.content)
    return PreparedStream(graph=graph, messages=messages, collect=collect)


async def run_chat_stream(
        graph: CompiledStateGraph,
        messages: list[BaseMessage],
        *,
        message_id: UUID,
        collect: ArtifactCollector | None = None,
        sink: SinkFn | None = None,
        trace: TraceContext | None = None,
) -> AsyncIterator[str]:
    """SSE 流主编排 —— 包 message_start / 驱动 adapter / 兜底 message_stop。

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

    try:
        # Langfuse:配了 key 才挂 callback;trace 归因走 config.metadata(langfuse_* 键)
        handler = get_langfuse_handler()
        config: dict[str, Any] = {}

        if handler is not None:
            config["callbacks"] = [handler]
            if trace is not None:
                if trace.name:
                    config["run_name"] = trace.name
                config["metadata"] = trace.to_config_metadata()

        events = graph.astream_events(
            {"messages": messages},
            version="v2",
            config=config or None,
        )

        async for event, payload in adapt_chat_stream(events):
            _feed_sink(sink, event, payload)
            yield sse_event(event, payload)

    finally:
        # 产物帧必须赶在 message_stop 之前 —— 前端收到 stop 就把这条消息收口了
        if collect is not None:
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

        # generator finally 兜底：自身 yield 也包 try，二次失败只 log 不再 raise
        try:
            stop_payload = {"id": str(message_id)}
            _feed_sink(sink, EventType.MESSAGE_STOP, stop_payload)
            yield sse_event(EventType.MESSAGE_STOP, stop_payload)

        except Exception:
            logger.exception("emit message_stop failed")
