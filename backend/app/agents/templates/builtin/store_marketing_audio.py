"""门店营销音频制作：查资料写稿 → 店员确认 → 后台制作 MP3。"""

from typing import Annotated, Any, ClassVar, Literal, TypedDict

from langchain.agents import create_agent
from langchain.agents.middleware import AgentMiddleware
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.graph.state import CompiledStateGraph
from pydantic import BaseModel, Field
from saq.job import Status

from app.agents.library.store_marketing_audio.presets import (
    DEFAULT_MUSIC_KEY,
    DEFAULT_VOICE_KEY,
    MUSIC_PRESETS,
    VOICE_PRESETS,
)
from app.agents.library.store_marketing_audio.promotions import PromotionLookupTool
from app.agents.stream_contract import emit_text
from app.agents.templates.base import GraphTemplate
from app.agents.templates.registry import register
from app.schemas.agent.interrupt_schema import AskAction, AskPayload, SelectField, TextField
from app.tools.base import CoCoTool
from app.tasks.queue import queue
from app.tasks.registry import PRODUCE_MARKETING_AUDIO


class BroadcastDraft(BaseModel):
    """写稿结果：播报原文 + 推荐音色。"""

    script: str = Field(description="要念出来的播报原文，不含标题、括号说明或语气提示")
    voice_key: str = Field(
        description="推荐音色：" + "；".join(f"{k}（{p.label}）" for k, p in VOICE_PRESETS.items()),
    )


class SubmitDraftTool(CoCoTool):
    """写稿 Agent 交稿用。不强制调用：资料不足时模型直接用文字说明，不交稿。"""

    name: str = "submit_broadcast_draft"
    display_name: str = "提交播报稿"
    description: str = "写好播报稿后调用，提交稿子和推荐音色给店员确认。调用后本步结束。"
    args_schema: type[BaseModel] = BroadcastDraft
    return_direct: bool = True

    async def _execute(self, script: str, voice_key: str) -> str:
        return "已提交，等待店员确认。"


class AudioState(TypedDict, total=False):
    messages: Annotated[list[BaseMessage], add_messages]
    draft: dict[str, str]   # 写稿结果：script / voice_key
    order: dict[str, str]   # 店员确认的制作内容：script / voice_key / music_key
    job_key: str            # 制作任务的键


_WRITER_PROMPT = """你为麦穗烘焙的店员写门店广播用的促销播报稿。

0. 店员的话不是播报需求时（闲聊、无意义输入），用一句话说明你能做什么，不调用任何工具。
1. 先看需求是否明确：本次主推的商品或系列、门店。缺了且无法从上文推断时，用 ask_human 一次问清。语气、音色这类偏好不要问。
2. 按需查资料：商品卖点查商品资料知识库；句子节奏和信息顺序参考播报话术知识库；涉及优惠、价格、时段必须用 lookup_promotions 核对。
3. 稿子里的商品事实和优惠只能来自查到的资料，查不到的优惠不写。
4. 篇幅以播报 20～30 秒为目标，最长不超过 60 秒（约 100～150 字）。句子短、口语化，适合大声喊出来；开头招呼路过的顾客，结尾再重复一次核心优惠。
5. 写好后用 submit_broadcast_draft 提交，稿子不要写在回复正文里。
6. 资料不足以写稿时（例如要推的商品查不到），不要硬写，直接说明缺了什么。"""

_ACTION_CONFIRM = "confirm"
_JOB_WAIT_SECONDS = 300
_STARTED = "开始制作音频，大约需要半分钟。"
_DONE = "音频做好了，可以直接试听，也可以下载后导入门店播放系统。"
_FAILED = "音频制作没有成功，请稍后重新发起。"
_STILL_RUNNING = "音频还在制作，稍后刷新页面查看。"


def _confirm_form(draft: dict[str, str]) -> AskPayload:
    return AskPayload(
        question="播报稿写好了，确认后开始制作音频",
        fields=[
            TextField(name="script", label="播报稿", default=draft["script"], multiline=True),
            SelectField(
                name="voice", label="音色",
                options=[p.label for p in VOICE_PRESETS.values()],
                default=VOICE_PRESETS[draft["voice_key"]].label,
            ),
            SelectField(
                name="music", label="配乐",
                options=[p.label for p in MUSIC_PRESETS.values()],
                default=MUSIC_PRESETS[DEFAULT_MUSIC_KEY].label,
            ),
        ],
        actions=[
            AskAction(id=_ACTION_CONFIRM, label="确认制作", style="primary"),
            AskAction(id="cancel", label="不做了"),
        ],
    )


def _key_by_label(presets: dict, label: object, default: str) -> str:
    return next((k for k, p in presets.items() if p.label == label), default)


@register
class StoreMarketingAudioTemplate(GraphTemplate):
    """店员说活动需求 → 查资料写播报稿 → 店员改稿选音色配乐 → 后台制作 MP3。"""

    key: ClassVar[str] = "store_marketing_audio"
    name: ClassVar[str] = "门店营销音频制作"
    description: ClassVar[str] = (
        "店员说一句活动需求，查商品、话术和活动资料写出门店播报稿；"
        "店员改稿、选音色和配乐后，制作可试听、下载的 MP3。"
    )
    config_fields: ClassVar[tuple[str, ...] | None] = ("chat_model", "knowledge")
    category: ClassVar[Literal["general", "business"]] = "business"

    def own_tools(self) -> list[BaseTool]:
        return [PromotionLookupTool(), SubmitDraftTool()]

    def build(
            self,
            *,
            chat_model: BaseChatModel,
            system_prompt: str | None,
            tools: list[BaseTool],
            middleware: list[AgentMiddleware] | None = None,
    ) -> CompiledStateGraph:
        writer = create_agent(
            model=chat_model,
            tools=tools,
            system_prompt=_WRITER_PROMPT,
            middleware=list(middleware or []),
        )

        async def write_node(state: AudioState, config: RunnableConfig) -> dict[str, Any]:
            messages = list(state["messages"])
            result = await writer.ainvoke({"messages": messages}, config)
            call = next((
                tc for m in reversed(result["messages"][len(messages):])
                if isinstance(m, AIMessage) for tc in m.tool_calls
                if tc["name"] == SubmitDraftTool.model_fields["name"].default
            ), None)
            if call is None:
                return {}
            draft = BroadcastDraft.model_validate(call["args"])
            voice_key = draft.voice_key if draft.voice_key in VOICE_PRESETS else DEFAULT_VOICE_KEY
            return {"draft": {"script": draft.script.strip(), "voice_key": voice_key}}

        def confirm_node(state: AudioState) -> dict[str, Any]:
            # 函数内 import：runtime 包初始化会 import runner → templates，放顶层成环
            from app.agents.runtime.ask import ask_user

            answer = ask_user(_confirm_form(state["draft"]))
            script = str(answer.values.get("script", "")).strip()
            if answer.action != _ACTION_CONFIRM or not script:
                return {}
            return {"order": {
                "script": script,
                "voice_key": _key_by_label(VOICE_PRESETS, answer.values.get("voice"), DEFAULT_VOICE_KEY),
                "music_key": _key_by_label(MUSIC_PRESETS, answer.values.get("music"), DEFAULT_MUSIC_KEY),
            }}

        async def produce_node(state: AudioState, config: RunnableConfig) -> dict[str, Any]:
            # thread_id 即本次回复的消息 ID（runner 的约定），产物挂到这条消息上
            message_id = config["configurable"]["thread_id"]
            job_key = f"marketing-audio-{message_id}"
            await PRODUCE_MARKETING_AUDIO.enqueue(key=job_key, message_id=message_id, **state["order"])
            return {"job_key": job_key, "messages": [emit_text(_STARTED)]}

        async def deliver_node(state: AudioState) -> dict[str, Any]:
            job = await queue.job(state["job_key"])
            if job is None:
                return {"messages": [emit_text(_FAILED)]}
            try:
                await job.refresh(until_complete=_JOB_WAIT_SECONDS)
            except TimeoutError:
                return {"messages": [emit_text(_STILL_RUNNING)]}
            done = job.status == Status.COMPLETE
            return {"messages": [emit_text(_DONE if done else _FAILED)]}

        builder = StateGraph(AudioState)
        builder.add_node("write", write_node)
        builder.add_node("confirm", confirm_node)
        builder.add_node("produce", produce_node)
        builder.add_node("deliver", deliver_node)
        builder.add_edge(START, "write")
        builder.add_conditional_edges(
            "write", lambda s: "confirm" if s.get("draft") else END, ["confirm", END]
        )
        builder.add_conditional_edges(
            "confirm", lambda s: "produce" if s.get("order") else END, ["produce", END]
        )
        builder.add_edge("produce", "deliver")
        builder.add_edge("deliver", END)
        return builder.compile()
