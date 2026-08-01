"""history_budget 的估算 + 切点单测 —— 纯内存，零 DB 零 LLM。

这一层为什么值得单测：它决定**哪些历史被永久压成摘要**。切错了不会报错，
只会让模型悄悄失忆（切多了）或者压缩白跑一趟（切少了），两种都不在日志里显形。

三组断言，性质不同：

1. **跳过规则** —— 带 subagent 戳的块、thinking 块不进上下文，所以也不能算进
   规模。这条错了后果最大：库里 358 个工具块有 282 个带戳，照原文数会把一条
   派活消息高估十几倍，于是「留最近 2 万」实际只留下一两千字。
2. **截断口径** —— 超限的工具结果在历史里只剩预览，不是原文。它必须跟
   assembler._cap_result 用同一条线（MAX_TOOL_OUTPUT_CHARS），两边跑偏估算就没意义。
3. **切点三规则** —— 上限不越界 / 落在一问一答边界 / 至少留一轮。第三条是防
   「最近一轮自己就超预算」时留出一段空历史，那会让模型连用户刚说的话都看不见。
"""

from uuid import UUID, uuid4

from app.agents.workspace.history_budget import (
    CHARS_PER_TOKEN,
    COMPACT_TRIGGER_TOKENS,
    CONTEXT_WINDOW_TOKENS,
    KEEP_TOKENS,
    _estimate_one,
    estimate_tokens,
    find_cutoff,
    should_compact,
)
from app.models import Message, MessageRole, SenderKind
from app.tools.base import MAX_TOOL_OUTPUT_CHARS

MEMBER_A = UUID("019f0d9b-1111-7000-8000-000000000001")

# _TOKENS_PER_MESSAGE 的副本 —— 测试里要按它反推字数。刻意不 import 私名：
# 它变了这里就该跟着算错、被下面 test_sized_helper_is_exact 当场抓住
PER_MESSAGE = 4


def msg(blocks: list[dict], kind: SenderKind = SenderKind.SUPERVISOR) -> Message:
    """造一条历史消息（同 test_view_context.py，不连库）。"""
    return Message(
        id=uuid4(),
        role=MessageRole.USER if kind == SenderKind.USER else MessageRole.ASSISTANT,
        sender_kind=kind,
        content=blocks,
    )


def tool(*, args: str = "{}", result=None, subagent: str | None = None) -> dict:
    return {
        "type": "tool_use", "id": "c1", "name": "search",
        "partial_json": args, "result_data": result, "status": "success",
        "subagent": subagent,
    }


def sized(kind: SenderKind, tokens: int) -> Message:
    """造一条估算值**恰好** = tokens 的消息（靠纯文本块凑字数）。"""
    chars = int((tokens - PER_MESSAGE) * CHARS_PER_TOKEN)
    return msg([{"type": "text", "text": "x" * chars}], kind)


def turns(sizes: list[int]) -> list[Message]:
    """按 user / assistant 交替造一串消息，sizes[i] = 第 i 条的 token 数。"""
    return [
        sized(SenderKind.USER if i % 2 == 0 else SenderKind.SUPERVISOR, n)
        for i, n in enumerate(sizes)
    ]


# ---------------------------------------------------------------- 估算

def test_sized_helper_is_exact():
    """先给测试工具本身立个哨兵 —— 下面所有切点用例都建立在它准确的前提上。"""
    assert _estimate_one(sized(SenderKind.USER, 1000)) == 1000
    assert estimate_tokens(turns([1000, 2000, 5000])) == 8000


def test_empty_is_zero():
    assert estimate_tokens([]) == 0


def test_每条消息都有固定开销():
    """空消息不是 0 —— <msg from> 标签、角色分隔符是实打实要占位的。"""
    assert _estimate_one(msg([])) == PER_MESSAGE


def test_subagent_块不计入():
    """成员的执行过程整段不回放，所以也不算规模。这条是本模块最关键的一条。"""
    plain = msg([tool(result="y" * 1000)])
    stamped = msg([tool(result="y" * 1000, subagent="member_019f0d9b")])

    assert _estimate_one(plain) > 400          # 1000 字 ÷ 2.5 ≈ 400
    assert _estimate_one(stamped) == PER_MESSAGE  # 整块跳过，只剩结构开销


def test_thinking_块不计入():
    """assembler 不回放 thinking（DeepSeek 要求推理内容不回喂）。"""
    assert _estimate_one(msg([{"type": "thinking", "thinking": "w" * 5000}])) == PER_MESSAGE


def test_超限结果按截断后算_不按原文():
    """26,000 字的 MCP 返回进历史只剩预览那一截，算成上万 token 就会压过头。"""
    huge = _estimate_one(msg([tool(result="y" * 26_000)]))

    assert huge < 300           # 截断后 620 字左右 ÷ 2.5
    assert huge < 26_000 / CHARS_PER_TOKEN / 10  # 比原文口径小一个数量级以上


def test_未超限结果按原文算():
    """没到线的结果是全量回放的，一个字都不能少算。"""
    size = MAX_TOOL_OUTPUT_CHARS - 100
    assert _estimate_one(msg([tool(result="y" * size)])) > size / CHARS_PER_TOKEN * 0.9


def test_截断的分界点就是工具输出上限():
    """恰好卡线的算全量，多一个字就掉进截断档 —— 与 _cap_result 同一条线。"""
    at_limit = _estimate_one(msg([tool(result="y" * MAX_TOOL_OUTPUT_CHARS)]))
    over_limit = _estimate_one(msg([tool(result="y" * (MAX_TOOL_OUTPUT_CHARS + 1))]))

    assert at_limit > over_limit * 2


def test_产物引用算文件名():
    ref = {
        "type": "artifact_ref", "artifact_id": str(MEMBER_A),
        "filename": "chart.svg", "size": 3598,
    }
    assert _estimate_one(msg([ref])) > PER_MESSAGE


# ---------------------------------------------------------------- 切点

def test_全放得下就不压():
    """预算够用时返回 0 —— 触发了压缩不代表一定压得动。"""
    assert find_cutoff(turns([1000] * 6), keep_tokens=10_000) == 0


def test_空历史不压():
    assert find_cutoff([], keep_tokens=10_000) == 0


def test_没有用户消息就不压():
    """没有 user 消息 = 没有可切的轮边界，宁可不切也不瞎切。"""
    only_assistants = [sized(SenderKind.SUPERVISOR, 5000) for _ in range(5)]
    assert find_cutoff(only_assistants, keep_tokens=1000) == 0


def test_留下的不超预算():
    """顶过预算的那条不要 —— 上限是 keep_tokens，只会少不会多。"""
    history = turns([1000] * 12)  # 共 12,000
    cutoff = find_cutoff(history, keep_tokens=10_000)

    assert cutoff > 0
    assert estimate_tokens(history[cutoff:]) <= 10_000


def test_切点落在用户消息上():
    """切在提问和回答中间会留下一个没头的回答，所以要往后推到 user。"""
    # 第 4 条特别大，往回累加会停在第 5 条（assistant）→ 应被推到第 6 条（user）
    history = turns([1000, 1000, 1000, 1000, 6000, 1000, 1000, 1000, 1000, 1000, 1000, 1000])
    cutoff = find_cutoff(history, keep_tokens=10_000)

    assert cutoff == 6
    assert history[cutoff].sender_kind == SenderKind.USER
    assert estimate_tokens(history[cutoff:]) <= 10_000


def test_最近一轮自己就超预算时至少留一轮():
    """留空了模型连用户刚说的话都看不见 —— 宁可这一轮超预算。"""
    history = turns([1000] * 12)
    cutoff = find_cutoff(history, keep_tokens=100)  # 任何一条都塞不下

    assert cutoff == 10                                    # 最后一条 user
    assert history[cutoff].sender_kind == SenderKind.USER
    assert len(history[cutoff:]) == 2                      # 一问一答，没留空


def test_不假设用户助手严格交替():
    """装配报 400 时 user 已落库、assistant 没落，库里真会有孤立的 user 消息。"""
    history = [
        sized(SenderKind.USER, 5000),
        sized(SenderKind.USER, 1000),      # 上一条没等到回答，用户又发了一句
        sized(SenderKind.SUPERVISOR, 1000),
    ]
    cutoff = find_cutoff(history, keep_tokens=3000)

    assert cutoff == 1
    assert history[cutoff].sender_kind == SenderKind.USER


def test_游标取切点前一条():
    """covers_until_message = messages[cutoff - 1]，摘要覆盖到它（含）为止。"""
    history = turns([1000] * 12)
    cutoff = find_cutoff(history, keep_tokens=10_000)

    material, cursor, kept = history[:cutoff], history[cutoff - 1], history[cutoff:]
    assert material[-1] is cursor          # 原料的最后一条就是游标
    assert cursor not in kept              # 游标不在保留段里，两边不重叠


# ---------------------------------------------------------------- 阈值

def test_阈值边界():
    """恰好等于不触发，超过才触发。"""
    assert not should_compact(COMPACT_TRIGGER_TOKENS)
    assert should_compact(COMPACT_TRIGGER_TOKENS + 1)
    assert not should_compact(0)


def test_两条线都从窗口派生():
    """换模型只该改 CONTEXT_WINDOW_TOKENS 一处，另外两条跟着走。

    **锁比例不锁字面量**：窗口是会变的（换模型、临时调小来验压缩链路），
    写死 170000 只会让这条测试变成「改窗口就红」的噪音。真正要守住的不变式
    是那两条线确实由窗口派生、且大小关系没被写反。
    """
    assert COMPACT_TRIGGER_TOKENS == int(CONTEXT_WINDOW_TOKENS * 0.85)
    assert KEEP_TOKENS == int(CONTEXT_WINDOW_TOKENS * 0.10)
    assert 0 < KEEP_TOKENS < COMPACT_TRIGGER_TOKENS < CONTEXT_WINDOW_TOKENS
