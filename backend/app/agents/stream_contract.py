"""模板层与 runtime 层之间的流式契约。

这里只放**两边都要认、又不该归属任何一方**的东西：模板负责打戳，adapter 负责认戳。

为什么单独开一个模块而不是塞进 runtime/events.py 或 templates/base.py：那两个包
互相 import 会成环 —— `runtime/__init__` 导出 runner，而 runner import templates，
于是 templates 只要碰一下 `app.agents.runtime.*` 就会触发这一圈。本模块挂在
`app.agents` 下（该包的 `__init__` 是空的），且只依赖 langchain，谁 import 都不会
拖起别人的包初始化。
"""

from langchain_core.messages import AIMessage
from langchain_core.runnables import Runnable

# 「内部工序」戳的 metadata 键。
#
# graph 模板的中间节点跑的是完整 agent，而节点必须透传 config —— 工具卡片要露脸、
# interrupt 要能冒泡、步数预算挂在它上面。可 config 一透传，那个 agent 的每个 token
# 就都流到前端了。但草稿 / 评审意见 / 检索材料是**工序**，不是交付物。
INTERNAL_STEP_KEY = "cocowork_internal_step"


def internal_step(agent: Runnable) -> Runnable:
    """把 graph 模板的中间工序标成「内部」：它的文字不流给前端，工具调用照常。

    不标会怎样，reflection 是最好的例子：用户依次看到草稿全文 → 一个孤零零的
    REVISE（内部协议词漏出去了）→ 一整篇自我批评 → 第二版草稿 → 又一篇批评 →
    最后定稿，而定稿跟最后那版草稿是同一份内容。协议词那条尤其没得商量：它在
    首行，流式发出去就收不回来。

    **这不是某个模板的特例，是 graph 这个形态的通病** —— 只要节点里有「不该外露
    的模型输出」，就该在这里过一道。

    工具调用刻意不静默：「正在搜索」这类进度是用户在中间步骤里唯一能看到的反馈，
    全静默的话检索那十几秒界面就是死的。

    用 with_config 注入 metadata 是 LangChain 的官方机制，metadata 随事件流原样传播
    到 adapter —— 同 adapter 里那条按官方 lc_source 戳拦下摘要中间件内部调用的先例。
    """
    return agent.with_config({"metadata": {INTERNAL_STEP_KEY: True}})


# 「这条消息要直接发给用户」戳。挂在 AIMessage.additional_kwargs 上，
# 与 INTERNAL_STEP_KEY 是一对：一个让模型的话静音，一个让代码的话发声。
EMIT_TEXT_KEY = "cocowork_emit_text"


def emit_text(content: str) -> AIMessage:
    """构造一条不经模型、直接流给用户的消息。

    graph 模板常有「这句话由代码决定」的时刻：reflection 的定稿（就是最后那版草稿，
    不该再烧一次模型重说一遍）、retrieve 的拒答（不让模型开口正是那一步的重点）。

    但 adapter 只翻译模型产生的事件，直接 `AIMessage(...)` 塞进 messages 的话前端
    一个字也收不到 —— reflection 的定稿此前就是这么丢的，用户看到的全是草稿和评审
    漏出来的过程，真正的成品从来没到达过。

    带戳的消息由 adapter 在 on_chain_stream 里认出来、补发成一个文本块。不带戳的
    一律不管：模型流过的消息已经逐 token 发过了，再发一遍就是重复。
    """
    return AIMessage(content=content, additional_kwargs={EMIT_TEXT_KEY: True})
