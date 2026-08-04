"""检索优先型：先查资料，再照着资料回答。

第二个 graph 形态的内置模板。与项目现有的 Agentic RAG（loop 模板挂知识库，
模型自己决定查不查、查几次）正好成对照：这里「查」是图的结构强制的第一步，
不是模型的一个选项。Perplexity 那类产品走的就是这个形状。

**这个模板的招牌是「答案必须来自检索」**，所以「查不到就不答」是它的底线，
由代码保证而非 prompt 保证 —— 详见 answer 节点开头那段短路。
"""

from typing import Annotated, ClassVar, TypedDict

from langchain.agents import create_agent
from langchain.agents.middleware import AgentMiddleware
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.graph.state import CompiledStateGraph

from app.agents.stream_contract import emit_text, internal_step
from app.agents.templates.base import GraphTemplate, compose_prompt
from app.agents.templates.registry import register


class RetrieveState(TypedDict, total=False):
    """图内状态。

    messages 是这张图对外的唯一接口：runner 传进来的是它，workspace 把这张图当
    节点嵌进去时也按它对接。findings 是纯中间产物，**不塞进 messages** —— 混进去
    会让外面看见本该是内部过程的东西（一整段材料抄录）。

    total=False：findings 在 research 跑完前不存在，answer 里用 .get() 取。
    """

    messages: Annotated[list[BaseMessage], add_messages]
    findings: str  # research 查回来的材料（工具原始返回）；空字符串 = 它一次工具都没调过


# 「不要回答用户的问题」必须写死：不写的话模型的本能是顺手把答案也给了，这一步
# 就变成了普通问答。
#
# 刻意不点名任何具体工具 —— 模板不认识用户挂了什么（可能是知识库、可能是搜索、
# 可能是某个数据库 MCP），让模型看工具描述自己判断。这也是模板能通吃各种数据源
# 的前提。
#
# 明确告诉它「不必复述查到的内容」：材料由 research_node 直接从工具返回里取，
# 它写的字一个都不会进 findings。不说这句的话它会本能地把材料重抄一遍 —— 那些
# 字既白烧 token，又会流到前端让用户把同一份内容看两遍。
_RESEARCH_PROMPT = """你现在的任务只有一件：为用户的问题查找资料。**不要回答问题本身。**

先看看你手头有哪些工具，自己判断哪些能查到用户要的东西，然后去查。用户的问题如果含有
指代（「它」「那个」之类），先结合上文把它还原成一个能查的完整问句再去查。

工具查回来的内容会被原样交给下一步使用，**你不需要复述、摘录或整理它们**。查完就结束，
不要给出结论，也不要总结你查到了什么。

如果手头的工具都查不到用户要的东西，直接说明情况即可，**绝对不要凭你已有的知识作答**。"""

# 作答脚手架。软约束，硬的那道在 answer 节点开头（没材料时模型根本不被调用）
_ANSWER_PROMPT = """请基于给你的检索材料回答用户的问题。

**只使用材料里有的内容**。材料里没有提到的，不要用你自己的知识补上 —— 哪怕你知道
答案。材料不足以回答时，直接说明缺了什么，这比编一个看起来完整的答案有用得多。

材料里若带有出处（链接、文档名、页码），在回答中一并给出。"""

_MATERIAL_TEMPLATE = """以下是为回答上述问题检索到的材料：

---
{findings}
---

请基于这些材料作答。"""

# 两句拒答文案。分两句而不是共用一句：「一个工具都没挂」和「挂了但这次没查到」
# 对用户是完全不同的两件事，共用一句的话，明明挂了知识库的人会看到「请先挂载
# 知识库」，只会以为系统坏了。
#
# 两个判据都是硬事实：tools 为空是数出来的，findings 为空是 research 节点里
# 数 ToolMessage 数出来的，都不经过模型。
_NO_TOOLS_REPLY = (
    "这个 Agent 没有挂载任何工具，无法检索资料，因此无法作答。\n\n"
    "请先为它挂上知识库、搜索类工具或提供查询能力的 MCP server，然后重试。"
)
_NO_FINDINGS_REPLY = "这次没有检索到可用于作答的资料，因此无法回答。"


@register
class RetrieveThenReadTemplate(GraphTemplate):
    """强制先检索、再基于检索结果回答；查不到就不答。"""

    key: ClassVar[str] = "retrieve_then_read"
    # 显示名用业界通用的模式名（RAG 文献里的 retrieve-then-read 管线），不自造中文名
    name: ClassVar[str] = "Retrieve-then-Read"
    description: ClassVar[str] = (
        "回答前强制检索一轮，再基于检索到的材料作答；未检索到资料时如实说明，不以既有知识补足。"
        "适用于需要引用外部资料的问题；常识性与纯推理性问题不适用，强制检索会引入无关结果干扰答案。"
        "需挂载知识库或搜索类工具。"
    )

    def build(
            self,
            *,
            chat_model: BaseChatModel,
            system_prompt: str | None,
            tools: list[BaseTool],
            middleware: list[AgentMiddleware] | None = None,
    ) -> CompiledStateGraph:
        """检索 → 作答，无循环。

        节点里跑的是完整 agent，不是裸的模型调用 —— 工具 / 护栏与 loop 模板拿到的
        完全一致，区别只在编排。
        """
        mw = list(middleware or [])

        # 装配期建好、节点闭包捕获：每进一次节点重建一个 agent 是白烧。
        #
        # internal_step：检索是工序，它的文字不该出现在用户面前 —— 模型在调工具的
        # 间隙必然会写点什么（「我来搜索一下…」），那些字既不进 findings，也不该
        # 流到前端占着答案前面的位置。工具调用本身照常露脸。
        researcher = internal_step(create_agent(
            model=chat_model,
            tools=tools,
            system_prompt=compose_prompt(_RESEARCH_PROMPT, system_prompt),
            middleware=mw,
        ))
        # **刻意不给工具**：answer 的活是读材料写答案。给了工具它会自己再查一遍，
        # research 那步就白跑了，而且「强制先检索再回答」这条线被它绕过去 ——
        # 模板会退化成一个多绕了一圈的 Agentic RAG。
        #
        # 注意这只是「不主动给」：middleware 是可以自己往里注入工具的（deepagents
        # 的 SubAgentMiddleware 会注入 task）。硬拆会把护栏一起拆掉，不值当；
        # 实际影响也小 —— 那个 middleware 只挂在 workspace 的 supervisor 上。
        answerer = create_agent(
            model=chat_model,
            tools=[],
            system_prompt=compose_prompt(_ANSWER_PROMPT, system_prompt),
            middleware=mw,
        )

        # 节点都收 config 并原样透传给内层 agent —— 事件流、interrupt 冒泡、
        # 步数预算全挂在它身上，断了内层就成了黑盒（前端什么也看不见）
        async def research_node(state: RetrieveState, config: RunnableConfig) -> dict:
            """查资料。findings 直接取工具的原始返回，不取模型转述的那一版。"""
            messages = list(state["messages"])
            result = await researcher.ainvoke({"messages": messages}, config)

            # **只看这个节点新产生的消息** —— 切掉传进去的那截历史。不切的话，
            # 上一轮对话里留下的 ToolMessage 会被当成这一轮的战果，从第二轮起
            # 「有没有真的查」就再也验不出来了。
            new_messages = result["messages"][len(messages):]

            # 取工具的原始返回，不取模型写的总结。三个理由：
            # ① 省掉一整次转述 —— 让模型把材料重写一遍要付一份输出 token，answer
            #    读那份转述又要付一份输入 token，同一份材料付三遍钱
            # ② 更保真 —— 工具返回的是原文，模型转述必然有损；这一步本来就是为了
            #    让 answer 拿到一手材料
            # ③ 顺带把「有没有真的查」这个判断合并掉：没调工具就没有 ToolMessage，
            #    拼出来就是空串，answer 那边一个 if 同时管两件事
            #
            # 带上工具名，answer 才分得清哪段材料来自哪个知识库 / 哪个搜索工具。
            # name 理论上可能为空（外部 MCP 工具不保证回填），兜一个中性占位。
            findings = "\n\n".join(
                f"【{m.name or '检索结果'}】\n{m.text}"
                for m in new_messages
                if isinstance(m, ToolMessage)
            )
            return {"findings": findings}

        async def answer_node(state: RetrieveState, config: RunnableConfig) -> dict:
            """照着材料作答。没材料就不答 —— 这是这个模板的底线。"""
            findings = state.get("findings", "")
            if not findings:
                # **代码短路，模型根本不被调用** —— 这是「不让它编」的硬保证。
                # 交给 prompt 说「没材料时请拒答」是靠不住的：模型完全可能觉得
                # 自己知道答案就直接答了，而那正是这个模板要消灭的东西。
                reply = _NO_TOOLS_REPLY if not tools else _NO_FINDINGS_REPLY
                # emit_text：这句是代码说的、没经过模型，裸 AIMessage 到不了前端
                return {"messages": [emit_text(reply)]}

            # 原始 messages 一并给它 —— 不知道用户问的是什么就没法判断材料够不够
            messages = [
                *state["messages"],
                HumanMessage(content=_MATERIAL_TEMPLATE.format(findings=findings)),
            ]
            result = await answerer.ainvoke({"messages": messages}, config)
            return {"messages": [AIMessage(content=result["messages"][-1].text)]}

        builder = StateGraph(RetrieveState)
        builder.add_node("research", research_node)
        builder.add_node("answer", answer_node)
        builder.add_edge(START, "research")
        builder.add_edge("research", "answer")
        builder.add_edge("answer", END)
        return builder.compile()
