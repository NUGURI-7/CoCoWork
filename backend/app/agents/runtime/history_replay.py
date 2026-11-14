"""把一条 Agent 回复的块还原成模型当初真实的调用形状：AIMessage(tool_calls) + 配对的 ToolMessage。

工作空间（应答者自己那条历史）与单 Agent 会话共用。超长结果按同一条线截断，
截断时附上 read_tool_result 的取回指引 —— 调用方据 has_oversized 挂上那个工具。
"""

from uuid import UUID

from langchain_core.messages import AIMessage, BaseMessage, ToolMessage

from app.agents.runtime.blocks import ContentBlock, TextBlock, ToolUseBlock
from app.core.identifiers import short_id
from app.tools.base import MAX_TOOL_OUTPUT_CHARS

# 配对 ToolMessage 在「没结局 / 没内容」时写什么 —— 空着不行，见 _tool_message
_RESULT_INTERRUPTED = "（调用被中断，没有结果）"
_RESULT_ERROR = "（工具执行出错）"
_RESULT_EMPTY = "（工具没有返回内容）"

# 超限结果保留的开头长度 —— 够模型认出「这是什么东西」，不够就让它自己取全文
REPLAY_PREVIEW_CHARS = 500


def replay_own_turn(
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
            _tool_message(b, cid) for cid, b in calls
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
            calls.append((b.id or f"{short_id(message_id)}-{seq}", b))
            seq += 1

    flush()
    return out


def _tool_message(b: ToolUseBlock, call_id: str) -> ToolMessage:
    """一个 tool_use 块 → 与之配对的结果消息。

    **必须配对**：API 硬性要求每个 tool_call 都跟一条结果，缺一条整轮报错。
    而库里 12% 的块是没结局的（用户中途点了停止）—— 所以「没有结果」也得
    表达成一条结果，不能省。这是压平方案当初白捡的便宜，改回原生形状就得
    自己付。
    """
    result = cap_result(b.result_text, b.id)
    if b.status == "success":
        return ToolMessage(
            content=result or _RESULT_EMPTY, tool_call_id=call_id, status="success"
        )
    fallback = _RESULT_ERROR if b.status == "error" else _RESULT_INTERRUPTED
    return ToolMessage(
        content=result or fallback, tool_call_id=call_id, status="error"
    )


def cap_result(result: str, tool_use_id: str) -> str:
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

    tool_use_id 传的是**库里那个 id**，不是 replay_own_turn 兜底造出来的那个 ——
    造出来的取不回来。为空时索性不给指引，免得教模型去调一个必然失败的调用。
    """
    if len(result) <= MAX_TOOL_OUTPUT_CHARS:
        return result
    head = (
        f"{result[:REPLAY_PREVIEW_CHARS]}\n\n"
        f"[结果过长已截断，完整 {len(result)} 字符"
    )
    if not tool_use_id:
        return f"{head}]"
    return f'{head}，需要全文请调 read_tool_result(tool_use_id="{tool_use_id}")]'


def has_oversized(blocks: list[ContentBlock]) -> bool:
    """这条消息里有没有会被 cap_result 截掉的结果。

    判据必须与 cap_result 一致 —— 包括「带 subagent 戳的块不回放、
    因此也不算数」这条。两边跑偏就会出现「挂了工具但没标记」或反过来。
    """
    return any(
        isinstance(b, ToolUseBlock)
        and not b.subagent
        and len(b.result_text) > MAX_TOOL_OUTPUT_CHARS
        for b in blocks
    )
