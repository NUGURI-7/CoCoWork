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
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage

from app.agents.runtime.blocks import (
    ArtifactRefBlock,
    ContentBlock,
    TextBlock,
    ToolUseBlock,
    parse_blocks,
)
from app.models import Message, SandboxArtifact, SenderKind
from app.services.sandbox.artifact import human_size
from app.tools.base import MAX_TOOL_OUTPUT_CHARS

# 非成员说话人的固定显示名(成员名字走 names map)
_SPEAKER_USER = "User"
SPEAKER_SUPERVISOR = "Supervisor"  # 公开：workspace.py 用作 supervisor 自我名，与下方 from 标签同源
_SPEAKER_MEMBER_FALLBACK = "Member"
# 系统标注的署名 —— 不是任何人的发言，只用来承载产物清单这类平台事实
_SPEAKER_SYSTEM = "System"

# tool 块结局 → 痕迹里的人话（None = 流被掐断没结局）
_STATUS_LABELS = {"success": "完成", "error": "出错"}

# 配对 ToolMessage 在「没结局 / 没内容」时写什么 —— 空着不行，见 _tool_message
_RESULT_INTERRUPTED = "（调用被中断，没有结果）"
_RESULT_ERROR = "（工具执行出错）"
_RESULT_EMPTY = "（工具没有返回内容）"

# 超限结果保留的开头长度 —— 够模型认出「这是什么东西」，不够就让它自己取全文
_REPLAY_PREVIEW_CHARS = 500


def member_key(member_id: UUID) -> str:
    """成员在派活协议里的机器键(task 的 subagent_type / 块上的 subagent 戳)。"""
    return f"member_{member_id.hex[:8]}"


def member_label(member_id: UUID, name: str) -> str:
    """成员的唯一显示标签(<msg from> / 花名册 / 行动痕迹共用) —— 名字#id8。"""
    return f"{name}#{member_id.hex[:8]}"


@dataclass(frozen=True)
class AssembledContext:
    """拼好的进场上下文 + 装配方需要知道的事实。

    truncated: 历史里有工具结果被截断过 —— 装配方据此决定挂不挂
        read_tool_result。**标记与工具必须同源**：有标记没工具 = 指死路，
        有工具没标记 = 白占位子还可能诱导瞎调。
    """

    messages: list[BaseMessage]
    truncated: bool


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

    视角化:viewer 自己说过的 → 原生的 AIMessage + ToolMessage(它当初真实的形状);
    其他人(用户 / Supervisor / 别的成员) → HumanMessage,内容统一包
    <msg from="名字"> 身份标签(user = "User")—— 所有说话人具名,身份靠读取不靠
    推断;唯一无标签的是当前轮输入(天然 = 正在对应答者说话的人)。

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
    ) -> AssembledContext:
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
        truncated = False

        # task 派活块入参里的 subagent_type（member_xxxx）→ 显示标签（名字#id8）
        member_labels = {
            member_key(mid): member_label(mid, name)
            for mid, name in names.items()
        }

        # viewer 若是成员,其 member_xxx 键 —— 用于把「派给我的活」翻成第二人称
        viewer_key = member_key(viewer.member_id) if viewer.member_id else ""

        for m in messages:
            blocks = parse_blocks(m.content)
            truncated = truncated or self._has_oversized(blocks)

            if self._is_me(m, viewer):
                # 自己那条走 API 的原生形状（tool_calls + 配对结果），不压平 ——
                # 压平会让「真调用过」这个事实掉进模型自己能写的文本通道
                out.extend(self._render_own(blocks, m.id))
            elif m.sender_kind == SenderKind.USER:
                # 用户不会**产出**文件（那是 agent 的交付区），但会**附**文件 ——
                # 拖进输入框的引用（决策 25），单独渲染
                text = "\n".join(
                    p for p in (self._text_of(blocks), self._render_attachments(blocks)) if p
                )
                if text:
                    # 历史里 user 也具名 —— 身份靠读取不靠推断,不留「负空间」
                    out.append(HumanMessage(f'<msg from="{_SPEAKER_USER}">{text}</msg>'))
            else:
                speaker = self._speaker_name(m, names)
                text = self._render_blocks(blocks, speaker, viewer_key, member_labels)
                if text:
                    out.append(HumanMessage(f'<msg from="{speaker}">{text}</msg>'))

            # 这条消息产出的文件 → 紧跟其后**独立一条**系统标注，不并进任何人的发言。
            # 并进去的后果实测过：模型看见自己上次的发言末尾挂着这行，下次就照抄一行
            # 出来（大小还是猜的），那串内部标记会被前端当正文渲染给用户看。
            # 独立一条之后它抄不了 —— 模型的输出永远是 assistant 角色，
            # 变不成这条 user 角色的消息。
            # 用 .get 不用 [] —— 传进来的是 defaultdict，下标取值会顺手插一个空
            # 列表进去，平白改掉调用方的数据
            produced = self._render_artifacts(artifacts.get(m.id, ()))
            if produced:
                out.append(HumanMessage(f'<msg from="{_SPEAKER_SYSTEM}">{produced}</msg>'))

        return AssembledContext(messages=out, truncated=truncated)

    def _render_artifacts(self, artifacts: Sequence[SandboxArtifact]) -> str:
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

    def _render_attachments(self, blocks: Sequence[ContentBlock]) -> str:
        """用户在这条消息里附过的文件 → 一行 <attachments> 标注（决策 25）。

        **刻意不带路径** —— 与本轮那份（inject_attachments 拼的）差别就在这里：
        那时文件刚灌进工作区、路径当场有效；而每一轮的工作区都是全新的空目录
        （决策 14a），历史里这些文件早已不在，给路径等于递给模型一个打不开的
        地址。它该看到的事实是「有过这么个文件」，要用就先 fetch_artifact 取回来。

        与 _render_artifacts 分成两个方法而不是合并：一个是**用户给的**、
        一个是 **agent 交付的**，来源不同、标签不同 —— 模型分得清才不会把
        自己没干过的事认成自己干的。
        """
        names = [
            f"{b.filename or '未命名文件'} ({human_size(b.size)})"
            for b in blocks
            if isinstance(b, ArtifactRefBlock)
        ]
        if not names:
            return ""
        return f"<attachments>{'、'.join(names)}</attachments>"

    def _is_me(self, m: Message, viewer: Viewer) -> bool:
        """这条是不是 viewer 本人发的 —— 决定它算「我」还是别人。"""
        if m.sender_kind != viewer.sender_kind:
            return False
        if viewer.sender_kind == SenderKind.MEMBER:
            return m.sender_member_id == viewer.member_id  # 还得是同一个成员
        return True

    def _render_own(
            self,
            blocks: list[ContentBlock],
            message_id: UUID,
    ) -> list[BaseMessage]:
        """viewer 自己那条消息 → AIMessage(tool_calls) + ToolMessage 的原生形状。

        **为什么不压成一段文字**：tool_calls 与 role="tool" 是 API 的结构化字段，
        role="tool" 那条是平台写进去的、模型伪造不了。一压平成
        `〔我 调用了工具 X → 完成〕`，这段事实就掉进了模型自己能写的文本通道 ——
        于是它下一轮照着再写一遍（实测：管家凭空编出整段派活 + 交付，
        而那一轮的工具调用记录是 0 条）。禁令拦不住，因为它只见过这一种样本。

        **切分单位 = 一次模型调用**：块序列里「文字 → 工具 → 文字 → 工具」本就是
        多次调用攒出来的，所以遇到工具之后再见文字就开下一条 AIMessage，
        还原成当初真实发生的形状。

        thinking 块不回放（现有行为不变）：DeepSeek 明确要求推理内容不回喂，
        Anthropic 的 thinking 块回喂要带签名，两边都不是这一层该碰的。
        带 subagent 戳的块同样跳过 —— 成员的交付内容已在 task 块的结果里。

        产物清单不在这里 —— 它是系统事实、不是它说过的话，由 build 单独发一条
        <msg from="System">。混进这条 AIMessage 会被模型当成「我的发言该长这样」
        照抄（实测复现过）。
        """
        out: list[BaseMessage] = []
        texts: list[str] = []
        calls: list[tuple[str, ToolUseBlock]] = []
        seq = 0

        def flush() -> None:
            """把攒着的一次调用吐成 AIMessage + 紧跟其后的配对结果。"""
            if not texts and not calls:
                return
            out.append(
                AIMessage(
                    content="\n\n".join(texts),
                    tool_calls=[
                        {
                            "name": b.name or "unknown_tool",
                            "args": b.input_args,
                            "id": cid,
                            "type": "tool_call",
                        }
                        for cid, b in calls
                    ],
                )
            )
            out.extend(
                self._tool_message(b, cid) for cid, b in calls
            )
            texts.clear()
            calls.clear()

        for b in blocks:
            if b.subagent:
                continue
            if isinstance(b, TextBlock) and b.text:
                if calls:
                    flush()  # 工具之后又出现文字 = 新一次模型调用
                texts.append(b.text)
            elif isinstance(b, ToolUseBlock):
                # id 是 tool_call ↔ 结果的配对凭据，缺一半 API 当场报错。
                # adapter 保证有（拿不到 id 根本不开块），这个兜底是给手改过的
                # 脏 jsonb 留的：拿消息 id + 序号造一个，跨消息也不会撞
                calls.append((b.id or f"{message_id.hex[:8]}-{seq}", b))
                seq += 1

        flush()
        return out

    def _tool_message(self, b: ToolUseBlock, call_id: str) -> ToolMessage:
        """一个 tool_use 块 → 与之配对的结果消息。

        **必须配对**：API 硬性要求每个 tool_call 都跟一条结果，缺一条整轮报错。
        而库里 12% 的块是没结局的（用户中途点了停止）—— 所以「没有结果」也得
        表达成一条结果，不能省。这是压平方案当初白捡的便宜，改回原生形状就得
        自己付。
        """
        result = self._cap_result(b.result_text, b.id)
        if b.status == "success":
            return ToolMessage(
                content=result or _RESULT_EMPTY, tool_call_id=call_id, status="success"
            )
        fallback = _RESULT_ERROR if b.status == "error" else _RESULT_INTERRUPTED
        return ToolMessage(
            content=result or fallback, tool_call_id=call_id, status="error"
        )

    def _cap_result(self, result: str, tool_use_id: str) -> str:
        """超长的工具结果 → 开头一截 + 取回指引；不超长的原样返回。

        **为什么要封顶**：结果进了历史就一直在，这个对话往后每一次回复都背着它。
        自家工具在单次执行时早就按 MAX_TOOL_OUTPUT_CHARS 截断了，没这层保护的
        是三条路 —— MCP 工具、deepagents 的文件工具、成员交付内容（实测 MCP
        单次返回过 26,049 字符 ≈ 13K token）。跨轮沿用同一个数：一次执行能进
        多少，历史里就是多少。

        **保留 500 而不是保留到上限**：留满上限等于没封顶。这 500 字不是「更小
        的上限」，是**标识** —— 够模型认出「这是那次路线规划的返回」，据此判断
        本次回复用不用得上，用得上再取全文。

        **必须给取回路**：只截不给读回来的办法，就是「看着像标准做法、其实照样
        丢信息」。全文躺在 messages.content 的 jsonb 里，read_tool_result 按 id
        查一条即得，不必另开表。

        tool_use_id 传的是**库里那个 id**，不是 _render_own 兜底造出来的那个 ——
        造出来的取不回来。为空时索性不给指引，免得教模型去调一个必然失败的调用。
        """
        if len(result) <= MAX_TOOL_OUTPUT_CHARS:
            return result
        head = (
            f"{result[:_REPLAY_PREVIEW_CHARS]}\n\n"
            f"[结果过长已截断，完整 {len(result)} 字符"
        )
        if not tool_use_id:
            return f"{head}]"
        return f'{head}，需要全文请调 read_tool_result(tool_use_id="{tool_use_id}")]'

    def _has_oversized(self, blocks: list[ContentBlock]) -> bool:
        """这条消息里有没有会被 _cap_result 截掉的结果。

        判据必须与 _cap_result 一致 —— 包括「带 subagent 戳的块不回放、
        因此也不算数」这条。两边跑偏就会出现「挂了工具但没标记」或反过来。
        """
        return any(
            isinstance(b, ToolUseBlock)
            and not b.subagent
            and len(b.result_text) > MAX_TOOL_OUTPUT_CHARS
            for b in blocks
        )

    def _render_blocks(
            self,
            blocks: list[ContentBlock],
            actor: str,
            viewer_key: str,
            member_labels: dict[str, str],
    ) -> str:
        """一条**别人的**消息的按块翻译：说过的话原样，干过的事一行痕迹 + 结果。

        actor = 这条消息的主语（第三方名字）。viewer 自己那条不走这里 ——
        它在 _render_own 里还原成原生的 tool_calls + ToolMessage。
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
                    self._render_tool(
                        b, actor, viewer_key, member_labels
                    )
                )
        return "\n\n".join(parts)

    def _render_tool(
            self,
            b: ToolUseBlock,
            actor: str,
            viewer_key: str,
            member_labels: dict[str, str],
    ) -> str:
        """一个**别人的** tool_use 块 → 一行行动痕迹 + 结果。"""
        status = _STATUS_LABELS.get(b.status, "中断")
        result = self._cap_result(b.result_text, b.id)
        if b.name != "task":
            header = f"〔{actor} 调用了工具 {b.name or '?'} → {status}〕"
            # 结果必须跟着回来 —— 只留一行「调用了什么」，等于告诉模型
            # 「发生过一件事」却不告诉它「查到了什么」，下一轮它就答不出
            # 上一轮的内容（这是被压平协议吃掉的另一半）
            return f"{header}\n结果：{result}" if result else header
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
        return f"{header}\n{who} 返回：\n{result}" if result else header

    def _text_of(self, blocks: list[ContentBlock]) -> str:
        """拼纯文本(只取 text 块) —— user 消息用,人类输入本来就只有 text。"""
        return "".join(
            b.text for b in blocks if isinstance(b, TextBlock) and b.text
        )

    def _speaker_name(self, m: Message, names: dict[UUID, str]) -> str:
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
