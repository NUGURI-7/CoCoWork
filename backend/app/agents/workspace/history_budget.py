"""跨回复历史压缩的度量层 —— 这段历史有多大、该从哪儿切。

不碰模型、不碰数据库,只回答两个问题:这批消息进上下文大约占多少 token,
以及「只留最近这么多 token」的话切点划在哪条消息上。

两个刻意的取舍:

1. **估算,不精确计数**。不引分词器(Dify 拿 GPT-2 数所有模型、Letta 拿 tiktoken
   数所有模型,都是明知不完全准照样用)。赌注很小 —— 压缩**什么时候**触发用的是
   API 上报的真值(`Conversation.context_tokens`),估算只决定**切点划在哪**,
   估偏了的后果就是留了 1.8 万或 2.5 万,不会导致该压的不压。

2. **与 viewer 无关**。同一段历史,管家看和成员看渲染出来不一样长(视角化),
   但切点只能有一个 —— 摘要是中性的一份全员共用,封存游标也只有一个。
   所以这里数的是不分视角的公共部分,不调 assembler 去渲染。
"""
from collections.abc import Iterable, Sequence
from math import ceil

from app.agents.runtime.blocks import (
    ArtifactRefBlock,
    TextBlock,
    ToolUseBlock,
    parse_blocks,
)
from app.agents.workspace.view_context_assembler import REPLAY_PREVIEW_CHARS
from app.models import Message, SenderKind
from app.tools.base import MAX_TOOL_OUTPUT_CHARS

# 模型上下文窗口 —— 当前锁 DeepSeek 的 20 万。下面两条线都从它派生,
# 换模型只改这一个数。
#
# 想验证压缩链路时可以临时调小(8_000 左右几轮就会触发一次),验完记得改回来。
CONTEXT_WINDOW_TOKENS = 200_000

# 超过这条线就压(窗口的 85%)。**判据是 `Conversation.context_tokens`** ——
# 上一轮模型实际上报的 input_tokens,不是本模块估出来的数。
# 一次回复内部那个压缩器(workspace.py 的 SummarizationMiddleware)用的也是这个数:
# 同一条「该压了」的线,两个消费方,不各写各的。
COMPACT_TRIGGER_TOKENS = int(CONTEXT_WINDOW_TOKENS * 0.85)

# 压缩之后往回留多少原文(窗口的 10%,deepagents 有 model profile 时的同款比例)。
# 留少一点、压缩间隔拉长,比留多一点反复压划算 —— 每压一次要烧一次模型调用,
# 而且会让 prompt cache 整个失效一次。
KEEP_TOKENS = int(CONTEXT_WINDOW_TOKENS * 0.10)

# 字符 → token 的换算率。中文约 1.5-1.7 字符一个 token、英文约 4,我们的历史是
# 中文对话 + 英文工具结果 + JSON 混着,取中间。**宁可往小捏** —— 设小了算出的
# token 数偏大、留得更少,只会更保守,不会撑爆窗口。
CHARS_PER_TOKEN = 2.5

# 每条消息的固定结构开销(`<msg from="X">` 标签、角色分隔符这类)。
# langchain 的 count_tokens_approximately 同样加了这么一笔(默认 3)
_TOKENS_PER_MESSAGE = 4

# 用户拖进来的产物引用渲染成 `文件名 (12KB)`,文件名之外的固定字数
_ARTIFACT_REF_CHARS = 12

# 超限的工具结果进历史后的实际字数 = 预览 + 那句「需要全文请调 read_tool_result」。
# **不是原文长度** —— 一个 26,000 字的 MCP 返回在历史里只占 600 字左右
_TRUNCATED_RESULT_CHARS = REPLAY_PREVIEW_CHARS + 120


def estimate_tokens(messages: Iterable[Message]) -> int:
    """这批消息进上下文之后大约占多少 token。"""
    return sum(_estimate_one(m) for m in messages)


def estimate_text_tokens(text: str) -> int:
    """一段纯文字大约多少 token —— 摘要正文记账用。

    刻意不用模型上报的 output_tokens:推理模型那个数**含它思考的部分**,
    而思考不进摘要正文,拿来当「摘要有多长」会虚高一大截。
    """
    return ceil(len(text) / CHARS_PER_TOKEN)


def should_compact(context_tokens: int) -> bool:
    """该压了吗 —— 收下的必须是**模型上报的真实值**,不是 estimate_tokens 的结果。

    这两笔账不通用:真实值含系统提示 + 工具定义(实测空对话地板就有 5,534),
    估算只覆盖历史消息。拿估算值来判这条线会永远判不到。
    """
    return context_tokens > COMPACT_TRIGGER_TOKENS


def find_cutoff(messages: Sequence[Message], keep_tokens: int = KEEP_TOKENS) -> int:
    """从最新往回留 keep_tokens,返回**保留段的起点下标**。

    调用方据此切两刀:
        messages[:cutoff]      → 要被压成摘要的原料
        messages[cutoff - 1]   → 写进 covers_until_message 的封存游标
        messages[cutoff:]      → 原样保留、照旧走视角化

    返回 0 = 没东西可压(全部都在预算内)。**触发了压缩不代表一定压得动** ——
    地板那 5,534 是系统提示和工具定义占的,历史本身可能并不长。

    三条规则,按顺序:
      ① 从最新往回累加,谁把总数顶过预算就不要谁 → 留下的**只会少于预算,不会多**
      ② 切点必须落在一条 user 消息前面,即按「一问一答」整块往回退 ——
         否则可能切在提问和回答中间,留下一个没头的回答
      ③ 至少留最近一轮。哪怕这一轮自己就超预算(管家一口气调了十几个工具),
         也不能留空 —— 留空了模型连用户刚说的话都看不见
    """
    turn_starts = [
        i for i, m in enumerate(messages) if m.sender_kind == SenderKind.USER
    ]
    if not turn_starts:
        return 0  # 没有用户消息 = 没有可切的轮边界

    # ① 从最新往回累加,找预算内能留的最早那条
    kept = 0
    earliest = len(messages)
    for i in range(len(messages) - 1, -1, -1):
        size = _estimate_one(messages[i])
        if kept + size > keep_tokens:
            break
        kept += size
        earliest = i

    # ② 对齐到轮边界 —— 往**后**推到最近的一条 user 消息。往后 = 留得更少,
    #    不会把预算撑破;往前扩就可能超预算。正常交替的历史里这一步只移 0 或 1 位,
    #    但那一位决定了保留段的开头是「用户问了什么」还是凭空一段回答。
    #    **不假设 user / assistant 严格交替** —— 装配阶段报 400 时 user 已落库、
    #    assistant 没落(见 stream.py 落 user 在装配之前),库里真会留下孤立的 user 消息
    aligned = next((s for s in turn_starts if s >= earliest), None)

    # ③ 一条都放不下时(aligned 为 None),退回到最后一轮的起点
    return turn_starts[-1] if aligned is None else aligned


def _estimate_one(message: Message) -> int:
    """一条 DB 消息 → 估算 token 数。

    数的是**渲染之后**的规模,不是 jsonb 原文的规模 —— 差别很大,见下面
    subagent 那条。跳过规则必须跟 assembler 一致,跑偏了估算就没意义。
    """
    chars = 0
    for block in parse_blocks(message.content):
        if block.subagent:
            # 成员的执行过程整段不回放(assembler 两条渲染路径都跳过它),
            # 数进来会把一条派活消息算成实际的十几倍 —— 库里 358 个工具块
            # 有 282 个带这个戳,照原文数会严重高估、导致留得远远不够
            continue
        if isinstance(block, TextBlock):
            chars += len(block.text)
        elif isinstance(block, ToolUseBlock):
            # 入参直接量 partial_json 的长度:回放时它被解析成 dict、再由 API
            # 序列化回去,字数基本原样,没必要为了估算多解析一遍
            chars += len(block.partial_json) + _result_chars(block)
        elif isinstance(block, ArtifactRefBlock):
            chars += len(block.filename) + _ARTIFACT_REF_CHARS
        # ThinkingBlock 不计 —— assembler 不回放它(DeepSeek 明确要求推理内容不回喂)
    return _TOKENS_PER_MESSAGE + ceil(chars / CHARS_PER_TOKEN)


def _result_chars(block: ToolUseBlock) -> int:
    """工具结果进历史后占多少字 —— 超限的只剩预览 + 取回指引。"""
    size = len(block.result_text)
    return size if size <= MAX_TOOL_OUTPUT_CHARS else _TRUNCATED_RESULT_CHARS
