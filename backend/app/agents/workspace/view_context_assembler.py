"""Workspace 对话的上下文组装器。

把 DB 里的对话历史,按「当前是谁在应答」的视角,重写成喂给该应答者的
LangChain messages。核心是「视角化」——同一段历史,从不同成员看,「我」和
「别人」是不同的。

与 runtime 的 to_lc_messages(通用、无身份)的区别:这里带 workspace 的多方
身份语义,所以独立成一层。进图前一次性构建(每轮对话重新拉历史拼),不是
loop 内的 middleware。
"""

from dataclasses import dataclass
from uuid import UUID

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from app.models import Message, SenderKind

# 非成员说话人的固定显示名(成员名字走 names map)
_SPEAKER_USER = "User"
SPEAKER_SUPERVISOR = "Supervisor"  # 公开：workspace.py 用作 supervisor 自我名，与下方 from 标签同源
_SPEAKER_MEMBER_FALLBACK = "Member"


@dataclass(frozen=True)
class Viewer:
    """谁在应答 —— 决定 build 时哪些消息算「我」。

    sender_kind: supervisor / member(user 不会是应答者)。
    member_id:   sender_kind == member 时为该成员 id,否则 None。
    """

    sender_kind: SenderKind
    member_id: UUID | None = None


class ViewContextAssembler:
    """把 workspace 对话历史按「谁在应答」的视角组装成 LLM messages。

    视角化:viewer 自己说过的 → AIMessage(「我」);其他人(用户 / Supervisor / 别的
    成员) → HumanMessage,内容包一层 <msg from="名字"> 身份标签,让应答者分得清
    谁说了什么。

    无状态:不持有 DB 连接、不拥有注入的 model,可跨请求复用,无需销毁 / 清理。
    model 仅为未来「AI 驱动的历史裁剪 / 压缩」预留,v1 不使用。
    """

    def __init__(self, model: BaseChatModel | None = None) -> None:
        self._model = model

    async def build(
            self,
            messages: list[Message],
            viewer: Viewer,
            names: dict[UUID, str],
    ) -> list[BaseMessage]:
        """DB 历史 + 视角 → 喂给应答者的 LLM messages(视角化 + 身份标签)。

        Args:
            messages: 按时间升序的对话历史(本轮 user 输入之前的快照)。
            viewer:   当前应答者(supervisor / 某成员)。
            names:    member_id → 成员名字,身份标签用;装配时从 workspace
                      members 构造,assembler 不自己查库。
        """

        out: list[BaseMessage] = []

        for m in messages:
            text = self._text_of(m)
            if not text:
                continue
            if self._is_me(m, viewer):
                out.append(AIMessage(text))  # 「我」说的
            elif m.sender_kind == SenderKind.USER:
                out.append(HumanMessage(text)) # 人类用户,无标签(默认对话方)
            else:
                speaker = self._speaker_name(m, names)
                out.append(HumanMessage(f'<msg from="{speaker}">{text}</msg>'))
        return out

    @staticmethod
    def _is_me(m: Message, viewer: Viewer) -> bool:
        """这条是不是 viewer 本人发的 —— 决定它算「我」还是别人。"""
        if m.sender_kind != viewer.sender_kind:
            return False
        if viewer.sender_kind == SenderKind.MEMBER:
            return m.sender_member_id == viewer.member_id  # 还得是同一个成员
        return True

    @staticmethod
    def _text_of(m: Message) -> str:
        """从消息 content blocks 拼纯文本(只取 text 块,跳过 thinking / tool)。"""
        return "".join(
            b["text"]
            for b in m.content
            if b.get("type") == "text" and b.get("text")
        )

    @staticmethod
    def _speaker_name(m: Message, names: dict[UUID, str]) -> str:
        """这条消息的说话人显示名(身份标签用)。"""
        if m.sender_kind == SenderKind.USER:
            return _SPEAKER_USER
        if m.sender_kind == SenderKind.SUPERVISOR:
            return SPEAKER_SUPERVISOR
        if m.sender_member_id is not None:
            return names.get(m.sender_member_id, _SPEAKER_MEMBER_FALLBACK)
        return _SPEAKER_MEMBER_FALLBACK
