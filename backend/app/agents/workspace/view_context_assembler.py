"""Workspace 对话的上下文组装器。

把 DB 里的对话历史,按「当前是谁在应答」的视角,重写成喂给该应答者的
LangChain messages。核心是「视角化」——同一段历史,从不同成员看,「我」和
「别人」是不同的。

与 runtime 的 to_lc_messages(通用、无身份)的区别:这里带 workspace 的多方
身份语义,所以独立成一层。进图前一次性构建(每轮对话重新拉历史拼),不是
loop 内的 middleware。
"""
from collections.abc import Sequence
from dataclasses import dataclass
from uuid import UUID

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from app.agents.runtime.blocks import ContentBlock, TextBlock, ToolUseBlock, parse_blocks
from app.models import Message, SandboxArtifact, SenderKind
from app.services.sandbox.artifact import human_size

# 非成员说话人的固定显示名(成员名字走 names map)
_SPEAKER_USER = "User"
SPEAKER_SUPERVISOR = "Supervisor"  # 公开：workspace.py 用作 supervisor 自我名，与下方 from 标签同源
_SPEAKER_MEMBER_FALLBACK = "Member"

# tool 块结局 → 痕迹里的人话（None = 流被掐断没结局）
_STATUS_LABELS = {"success": "完成", "error": "出错"}


def member_key(member_id: UUID) -> str:
    """成员在派活协议里的机器键(task 的 subagent_type / 块上的 subagent 戳)。"""
    return f"member_{member_id.hex[:8]}"


def member_label(member_id: UUID, name: str) -> str:
    """成员的唯一显示标签(<msg from> / 花名册 / 行动痕迹共用) —— 名字#id8。"""
    return f"{name}#{member_id.hex[:8]}"


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
    成员) → HumanMessage,内容统一包 <msg from="名字"> 身份标签(user = "User")——
    所有说话人具名,身份靠读取不靠推断;唯一无标签的是当前轮输入(天然 = 正在
    对应答者说话的人)。

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
            artifacts: dict[UUID, list[SandboxArtifact]],
    ) -> list[BaseMessage]:
        """DB 历史 + 视角 → 喂给应答者的 LLM messages(视角化 + 身份标签)。

        Args:
            messages: 按时间升序的对话历史(本轮 user 输入之前的快照)。
            viewer:   当前应答者(supervisor / 某成员)。
            names:    member_id → 成员名字,身份标签用;装配时从 workspace
                      members 构造,assembler 不自己查库。
            artifacts: message_id → 该消息产出的文件(决策 24)。同 names,
                      由装配方查好传入。**刻意不给默认值** —— 给了的话哪天
                      调用方漏传,签名对、类型对、不报错,只是产物清单静默消失。
        """

        out: list[BaseMessage] = []

        # task 派活块入参里的 subagent_type（member_xxxx）→ 显示标签（名字#id8）
        member_labels = {
            member_key(mid): member_label(mid, name)
            for mid, name in names.items()
        }

        # viewer 若是成员,其 member_xxx 键 —— 用于把「派给我的活」翻成第二人称
        viewer_key = member_key(viewer.member_id) if viewer.member_id else ""

        for m in messages:
            blocks = parse_blocks(m.content)
            # 这条消息产出的文件。用 .get 不用 [] —— 传进来的是 defaultdict,
            # 下标取值会顺手插一个空列表进去,平白改掉调用方的数据
            produced = self._render_artifacts(artifacts.get(m.id, ()))
            if self._is_me(m, viewer):
                text = self._render_blocks(blocks, "我", viewer_key, member_labels)
                text = "\n".join(p for p in (text, produced) if p)
                if text:
                    out.append(AIMessage(text))  # 「我」说的 + 我干过的事 + 我产出的文件
                continue
            if m.sender_kind == SenderKind.USER:
                # 用户消息不会产出文件,这一支不并
                text = self._text_of(blocks)
                if text:
                    # 历史里 user 也具名 —— 身份靠读取不靠推断,不留「负空间」
                    out.append(
                        HumanMessage(f'<msg from="{_SPEAKER_USER}">{text}</msg>')
                    )
                continue
            speaker = self._speaker_name(m, names)
            text = self._render_blocks(blocks, speaker, viewer_key, member_labels)
            text = "\n".join(p for p in (text, produced) if p)
            if text:
                out.append(HumanMessage(f'<msg from="{speaker}">{text}</msg>'))

        return out

    @staticmethod
    def _render_artifacts(artifacts: Sequence[SandboxArtifact]) -> str:
        """这条消息产出的文件 → 一行 <artifacts> 标注（决策 24）。

        用 XML 而不是自然语言括号：它跟正文长得越不像,模型越分得清
        「这是系统标的,不是我写的」。形状与 skill 清单的 <available_skills> 同源。

        **文件名不转义**（决策 24 落地时定）：脚本要是起了个带 `</artifacts>`
        的名字,确实能伪造出一段假标注 —— 但 skill 是用户自己挂的、跑的是它自己的
        代码,与「/skills 不做只读」同一条理由（C.3 末尾）。等用户上传那一刀落地、
        脚本真成了不可信输入时,改成在**收产物那层**拒掉特殊字符 ——
        堵在入口比堵在渲染处干净,而且只堵一处。
        """
        if not artifacts:
            return ""
        items = "、".join(f"{a.filename} ({human_size(a.size)})" for a in artifacts)
        return f"<artifacts>{items}</artifacts>"

    @staticmethod
    def _is_me(m: Message, viewer: Viewer) -> bool:
        """这条是不是 viewer 本人发的 —— 决定它算「我」还是别人。"""
        if m.sender_kind != viewer.sender_kind:
            return False
        if viewer.sender_kind == SenderKind.MEMBER:
            return m.sender_member_id == viewer.member_id  # 还得是同一个成员
        return True

    @staticmethod
    def _render_blocks(
            blocks: list[ContentBlock],
            actor: str,
            viewer_key: str,
            member_labels: dict[str, str],
    ) -> str:
        """一条消息的按块翻译：说过的话原样，干过的事一行痕迹。

        actor = 这条消息的主语(「我」或第三方名字)，痕迹跟着换人称。
        带 subagent 戳的块 = 成员执行过程，跳过 —— 最终产出已在
        task 块的 result_data 里，过程重复渲染只会撑大上下文。
        """
        parts: list[str] = []
        for b in blocks:
            if b.subagent:
                continue
            if isinstance(b, TextBlock) and b.text:
                parts.append(b.text)
            elif isinstance(b, ToolUseBlock):
                parts.append(
                    ViewContextAssembler._render_tool(
                        b, actor, viewer_key, member_labels
                    )
                )
        return "\n\n".join(parts)

    @staticmethod
    def _render_tool(
            b: ToolUseBlock,
            actor: str,
            viewer_key: str,
            member_labels: dict[str, str],
    ) -> str:
        """一个 tool_use 块 → 一行行动痕迹（task 派活块额外带成员产出）。"""
        status = _STATUS_LABELS.get(b.status, "中断")
        if b.name != "task":
            return f"〔{actor} 调用了工具 {b.name or '?'} → {status}〕"
        # task 派活块：入参里挖 派给谁 + 任务描述，结果 = 成员产出。
        # 派活对象是 viewer 本人时用第二人称 —— 成员由此认出自己受过的委派
        args = b.input_args
        target = args.get("subagent_type") or ""
        who = (
            "你" if target and target == viewer_key
            else member_labels.get(target, target or "成员")
        )
        desc = args.get("description") or "（任务描述缺失）"
        header = f"〔{actor} 派活给 {who}：{desc} → {status}〕"
        if isinstance(b.result_data, str) and b.result_data.strip():
            return f"{header}\n{who} 返回：\n{b.result_data}"
        return header

    @staticmethod
    def _text_of(blocks: list[ContentBlock]) -> str:
        """拼纯文本(只取 text 块) —— user 消息用,人类输入本来就只有 text。"""
        return "".join(
            b.text for b in blocks if isinstance(b, TextBlock) and b.text
        )

    @staticmethod
    def _speaker_name(m: Message, names: dict[UUID, str]) -> str:
        """这条消息的说话人显示名(身份标签用)。"""
        if m.sender_kind == SenderKind.USER:
            return _SPEAKER_USER
        if m.sender_kind == SenderKind.SUPERVISOR:
            return SPEAKER_SUPERVISOR
        if m.sender_member_id is not None:
            name = names.get(m.sender_member_id)
            if name:
                return member_label(m.sender_member_id, name)
        return _SPEAKER_MEMBER_FALLBACK
