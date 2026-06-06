"""LangChain chat model 工厂 —— ModelSlot → BaseChatModel。

为什么函数形态而非静态实例：
- 每次请求重建凭证 / 配置（防 Provider 改 base_url / key 后实例不刷新）
- Workspace 跨节点换模型场景（Supervisor 用 A、NPC 各用各的）天然支持
- BaseChatModel 本身就是廉价对象，重建无性能负担

凭证解析：Model 级覆盖优先、空则 fallback Provider 级（沿用 ModelClient 同款）。
"""

import logging
from collections.abc import AsyncIterator

from langchain.chat_models import init_chat_model
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langgraph.graph.state import CompiledStateGraph
from uuid_utils import uuid7

from app.agents.runtime.adapter import adapt_chat_stream
from app.agents.runtime.events import EventType, sse_event
from app.agents.templates import get_template
from app.core.encryption import decrypt
from app.core.exceptions import ValidationException
from app.models import Agent
from app.models.model import AIModel
from app.schemas.agent.chat_schema import ChatStreamRequest
from app.schemas.agent.chat_schema import ContentBlock, HistoryMessage
from app.schemas.agent.config_schema import AgentConfig
from app.schemas.agent.config_schema import ModelSlot

logger = logging.getLogger(__name__)

# provider_type → LangChain model_provider
# OpenAI 兼容 provider 全走 "openai"（靠 base_url 区分上游），只有 Anthropic 走官方协议。
# 未知类型 fallback "openai" —— 最宽容 + log warning。

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
    base_url = ai_model.base_url or provider.base_url
    api_key_encrypted = ai_model.api_key_encrypted or provider.api_key_encrypted
    api_key = decrypt(api_key_encrypted)

    lc_provider = _resolve_lc_provider(provider.provider_type)

    # params：exclude_none —— 让 LangChain / 各 provider 用自己默认
    params = slot.params.model_dump(exclude_none=True)

    return init_chat_model(
        model=ai_model.model_name,
        model_provider=lc_provider,
        base_url=base_url,
        api_key=api_key,
        **params
    )


def _content_to_text(blocks: list[ContentBlock]) -> str:
    """ContentBlock 数组拼成 str。

    P0 union 只有 TextBlock，直接拼 `text` 字段。P1 加 ToolUseBlock /
    ImageBlock 时这里扩 multi-modal 块（HumanMessage 支持 list-of-content
    multi-modal 形态）。
    """
    return "".join(b.text for b in blocks)


def _to_lc_messages(
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


async def prepare_stream(
        agent: Agent,
        request: ChatStreamRequest,
) -> tuple[CompiledStateGraph, list[BaseMessage]]:
    """SSE 流开起来前的同步装配 —— 配置校验 / 取模板 / 装 chat model / 装 graph。

    所有可能 raise 的逻辑在此完成 —— FastAPI handler 接 ValidationException → 400 JSON。
    一旦返回 (graph, messages)，调用方就可以放心交给 StreamingResponse（不再有 raise 风险）。

    Raises:
        ValidationException: agent.config 形态错 / 模板不在册 / chat 模型未配 / 槽位类型错
    """
    cfg = AgentConfig.model_validate(agent.config)

    if cfg.models.chat is None:
        raise ValidationException("Agent 未配置 chat 模型")

    template = get_template(agent.template)
    if template is None:
        raise ValidationException(f"模板不在册：{agent.template}")

    chat_model = await build_chat_model(cfg.models.chat)

    graph = template.build(
        chat_model=chat_model,
        system_prompt=cfg.system_prompt,
        tools=[]
    )

    messages = _to_lc_messages(request.history, request.content)
    return graph, messages


async def run_chat_stream(
        graph: CompiledStateGraph,
        messages: list[BaseMessage],
) -> AsyncIterator[str]:
    """SSE 流主编排 —— 包 message_start / 驱动 adapter / 兜底 message_stop。

    异常分层：
    - 配置 / 模板 / 模型校验 → prepare_stream raise → FastAPI 400 JSON（SSE 还没起）
    - LLM 调用 / adapter 内部 → adapter 全部 try/except 翻成 error 帧（脱敏 + 关块）
    - message_stop → finally 兜底必发（前端靠它关活气泡，光标不卡）
    """
    message_id = str(uuid7())

    yield sse_event(EventType.MESSAGE_START, {
        "id": message_id,
        "role": "assistant",
    })
    try:
        events = graph.astream_events(
            {"messages": messages},
            version="v2",
        )
        async for sse in adapt_chat_stream(events):
            yield sse

    finally:
        # generator finally 兜底：自身 yield 也包 try，二次失败只 log 不再 raise
        try:
            yield sse_event(EventType.MESSAGE_STOP, {"id": message_id})
        except Exception:
            logger.exception("emit message_stop failed")
