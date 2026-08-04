"""反思精修型：先出稿，自审一遍指出缺漏，再重写。

第一个 graph 形态的内置模板。与 loop 的区别只在编排 —— 节点里跑的仍是完整
agent（同样的工具 / 知识库 / 护栏），不是功能阉割版。
"""

from typing import Annotated, ClassVar, TypedDict

from langchain.agents import create_agent
from langchain.agents.middleware import AgentMiddleware
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.graph.state import CompiledStateGraph

from app.agents.templates.base import GraphTemplate, compose_prompt
from app.agents.templates.registry import register


class ReflectionState(TypedDict, total=False):
    """图内状态。

    messages 是这张图对外的唯一接口：runner 传进来的是它，workspace 把这张图
    当节点嵌进去时也按它对接。所以中间产物（草稿 / 评审意见）**单独存字段、
    不塞进 messages** —— 混进去会污染对外的对话历史，让外面看见本该是内部
    过程的东西。

    total=False：draft / feedback / iteration 首轮还不存在，节点里用 .get() 取。
    """

    messages: Annotated[list[BaseMessage], add_messages]
    draft: str  # 当前这版草稿
    feedback: str  # 上一轮评审留下的修改意见，喂回生成节点
    iteration: int  # 已经评审过几轮，用来卡上限
    approved: bool  # 上一轮评审的结论，条件边据此决定收尾还是回炉


_DRAFT_PROMPT = """请完成用户提出的要求，直接给出成稿，不要解释你的思路。

如果收到了修改意见，请针对每一条做出修改，重新给出完整的一版，而不是只回复改动部分。"""

# 三处刻意写死的措辞：
# - 「不是重写它」—— 不写这句模型的本能是直接给一版新的，评审节点就变成第二个
#   生成节点，循环失去意义
# - 「可以使用工具核对事实」—— 评审不接外部依据的话只能审文字通顺，审不出硬伤
# - 「判断从严」—— 模型倾向给自己的稿子放行，不加这句第一轮基本都直接 PASS
#
# 结论用首行文字约定、**不用框架的结构化输出**：那条路底层是绑一个工具再强制
# tool_choice=required，实测在开着思考模式的推理模型上直接 400
# （"tool_choice does not support being set to required in thinking mode"）。
# 内置模板要在用户配的任意模型上跑，赌任何一种结构化输出能力都会在某些模型上碎掉
_CRITIQUE_PROMPT = """现在你的任务是审查下面这版稿子，不是重写它。

按两个维度检查：**多余的**（跑题、重复、无根据的话）和**缺失的**（用户要求里没被覆盖到的部分）。
必要时可以使用你的工具核对事实，不要仅凭印象判断对错。

**回复格式（必须遵守）**：第一行只写一个词 —— 稿子已达要求写 PASS，需要修改写 REVISE。
从第二行开始写审查结论，这部分用户会看到，要像话：
- 写 REVISE 时，逐条说明问题出在哪、该怎么改。
- 写 PASS 时，用一句话说清你核对了哪几项、结论是什么，不要只留一个孤零零的 PASS。

判断从严：没有具体问题可写的时候才算 PASS。"""


def _parse_critique(text: str) -> tuple[bool, str]:
    """拆评审回复：首行是结论，其余是意见。

    首行两侧的 markdown 记号要剥掉 —— 模型很爱写成 **PASS**。

    读不出结论时一律当作「要改」，往安全的那边倒：多审一轮最多浪费一次模型
    调用，而误判成通过会把没审过的稿子直接交出去。
    """
    head, _, rest = text.partition("\n")
    return head.strip().strip("*#`>「」 ").upper().startswith("PASS"), rest.strip()

# 最多评审几轮。写死不给用户配 —— 轮数属于「这个模板怎么干活」，是模板作者的
# 决定（ChatGPT 的 Deep Research 也不给「查几轮」的旋钮）
_MAX_ITERATIONS = 2

_REVISE_TEMPLATE = """这是你上一版稿子收到的修改意见：

{feedback}

请针对每一条修改，重新给出完整的一版。"""

_REVIEW_TEMPLATE = """这是待审查的稿子：

---
{draft}
---

请按上面的要求审查它。"""


@register
class ReflectionTemplate(GraphTemplate):
    """先出稿 → 自审 → 重写，最多两轮。"""

    key: ClassVar[str] = "reflection"
    # 显示名用 Anthropic《Building Effective Agents》的模式术语，不另起中文名 ——
    # 将来加的 Prompt Chaining / Routing / Parallelization 都在同一套词汇里
    name: ClassVar[str] = "Evaluator-Optimizer"
    description: ClassVar[str] = (
        "先出一版稿，再自己审一遍指出多余和缺漏，然后照着意见重写，最多两轮。"
        "适合一遍写不好、对质量有要求的任务。"
    )

    def build(
            self,
            *,
            chat_model: BaseChatModel,
            system_prompt: str | None,
            tools: list[BaseTool],
            middleware: list[AgentMiddleware] | None = None,
    ) -> CompiledStateGraph:
        """出稿 → 审稿 → （不过就回炉）→ 收尾。

        节点里跑的是完整 agent，不是裸的模型调用 —— 工具 / 知识库 / 护栏
        与 loop 模板拿到的完全一致，区别只在编排。
        """
        mw = list(middleware or [])

        # 装配期建好、节点闭包捕获：每进一次节点重建一个 agent 是白烧
        drafter = create_agent(
            model=chat_model,
            tools=tools,
            system_prompt=compose_prompt(_DRAFT_PROMPT, system_prompt),
            middleware=mw,
        )
        critic = create_agent(
            model=chat_model,
            tools=tools,
            system_prompt=compose_prompt(_CRITIQUE_PROMPT, system_prompt),
            middleware=mw,
        )

        # 节点都收 config 并原样透传给内层 agent —— 事件流、interrupt 冒泡、
        # 步数预算全挂在它身上，断了内层就成了黑盒（前端什么也看不见）
        async def draft_node(state: ReflectionState, config: RunnableConfig) -> dict:
            """出稿。带着上一轮意见回来时，把上一版和意见一并给它。"""
            messages = list(state["messages"])
            feedback = state.get("feedback", "")
            if feedback:
                messages.append(AIMessage(content=state.get("draft", "")))
                messages.append(
                    HumanMessage(content=_REVISE_TEMPLATE.format(feedback=feedback))
                )
            result = await drafter.ainvoke({"messages": messages}, config)
            return {"draft": result["messages"][-1].text}

        async def critique_node(state: ReflectionState, config: RunnableConfig) -> dict:
            """审稿。原始 messages 一并给它 —— 不知道用户要什么就判不出「缺失」。"""
            messages = list(state["messages"])
            messages.append(
                HumanMessage(content=_REVIEW_TEMPLATE.format(draft=state.get("draft", "")))
            )
            result = await critic.ainvoke({"messages": messages}, config)
            approved, feedback = _parse_critique(result["messages"][-1].text)
            return {
                "approved": approved,
                "feedback": feedback,
                "iteration": state.get("iteration", 0) + 1,
            }

        async def finalize_node(state: ReflectionState) -> dict:
            """把定稿放回 messages —— 这张图对外只交付这一条。"""
            return {"messages": [AIMessage(content=state.get("draft", ""))]}

        def route(state: ReflectionState) -> str:
            """过了、或者轮数用完，收尾；否则回去改。"""
            if state.get("approved") or state.get("iteration", 0) >= _MAX_ITERATIONS:
                return "finalize"
            return "draft"

        builder = StateGraph(ReflectionState)
        builder.add_node("draft", draft_node)
        builder.add_node("critique", critique_node)
        builder.add_node("finalize", finalize_node)
        builder.add_edge(START, "draft")
        builder.add_edge("draft", "critique")
        builder.add_conditional_edges("critique", route, ["draft", "finalize"])
        builder.add_edge("finalize", END)
        return builder.compile()
