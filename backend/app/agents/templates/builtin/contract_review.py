"""合同初审：取合同 → 六项检查依次执行 → 给出结论和按严重程度排序的问题清单。"""

import operator
from dataclasses import dataclass
from datetime import date
from typing import Annotated, Any, ClassVar, Literal, TypedDict

from langchain.agents import create_agent
from langchain.agents.middleware import AgentMiddleware
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_core.runnables import RunnableConfig
from langchain_core.tools import BaseTool
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from langgraph.graph.state import CompiledStateGraph
from pydantic import BaseModel, Field

from app.agents.library.contract_review.registry import CompanyLookupTool
from app.agents.library.contract_review.samples import SAMPLES, load_sample
from app.agents.library.contract_review.standards import (
    DiscountRulesTool,
    PaymentTermsTool,
    ProductCatalogTool,
    StandardClausesTool,
)
from app.agents.stream_contract import emit_text, internal_step
from app.agents.templates.base import GraphTemplate
from app.agents.templates.registry import register
from app.schemas.agent.interrupt_schema import AskAction, AskPayload, SelectField, TextField
from app.tools.base import CoCoTool
from app.tools.builtin.calculator import CalculatorTool

Level = Literal["high", "medium", "low"]

_LEVELS: dict[Level, tuple[str, str]] = {
    "high": ("🔴", "必须修改"),
    "medium": ("🟡", "建议协商"),
    "low": ("🔵", "补正即可"),
}


class Issue(BaseModel):
    level: Level = Field(
        description="high=必须修改（违反公司硬性规定、主体错误、对我方明显不利的条款改动）；"
                    "medium=建议协商（与公司标准不一致但可以谈）；low=补正即可（漏填、格式、未勾选、笔误）",
    )
    problem: str = Field(description="一句话说清问题，不超过 40 字")
    location: str = Field(description="问题所在位置，如「第三条」「合同首部」")
    quote: str = Field(default="", description="合同原文摘录，越短越好；合同里没有对应内容时留空")
    suggestion: str = Field(description="一句话说怎么改，不超过 60 字")


class CheckResult(BaseModel):
    issues: list[Issue] = Field(default_factory=list, description="本项发现的问题；没有问题时为空列表")


class SubmitCheckResultTool(CoCoTool):
    """检查 Agent 交结果用：问题以结构化数据登记，清单由代码统一渲染。"""

    name: str = "submit_check_result"
    display_name: str = "登记检查结果"
    description: str = "本项检查完成后调用一次，登记发现的问题（没有问题就传空列表）。调用后本项结束。"
    args_schema: type[BaseModel] = CheckResult
    return_direct: bool = True

    async def _execute(self, issues: list[dict[str, Any]]) -> str:
        return "已登记。"


class ReviewState(TypedDict, total=False):
    messages: Annotated[list[BaseMessage], add_messages]
    contract: str                                          # 合同全文
    issues: Annotated[list[dict[str, Any]], operator.add]  # 各项登记的问题，按执行顺序累加


@dataclass(frozen=True)
class Check:
    key: str
    title: str
    tool_names: tuple[str, ...]
    instruction: str


_SUBMIT = SubmitCheckResultTool.model_fields["name"].default
_CALC = CalculatorTool.model_fields["name"].default
_COMPANY = CompanyLookupTool.model_fields["name"].default
_CATALOG = ProductCatalogTool.model_fields["name"].default
_DISCOUNT = DiscountRulesTool.model_fields["name"].default
_PAYMENT = PaymentTermsTool.model_fields["name"].default
_CLAUSES = StandardClausesTool.model_fields["name"].default

CHECKS: tuple[Check, ...] = (
    Check(
        "party", "签约对象", (_COMPANY,),
        "找出甲方全称（不是最终用户），用 lookup_company_registry 查询工商信息，核对：\n"
        "- 甲方全称与工商登记是否一致，经营状态是否正常\n"
        "- 合同首部和第二条开票信息中的甲方税号是否与统一社会信用代码一致\n"
        "只管以上几点。联系人、电话、日期、地点不归本项。",
    ),
    Check(
        "basics", "基本信息", (),
        "核对合同首部和第五条的填写情况：\n"
        "- 甲方、乙方、最终用户（如有）的联系人、联系电话、电子邮箱是否填写\n"
        "- 格式：固定电话为区号 + 7～8 位（杭州、无锡等地为 8 位），手机号 11 位，邮箱须有完整域名后缀\n"
        "- 签订日期、签订地点（具体到城市）是否填写，签订日期不得晚于今天\n"
        "同一类缺失合并成一条。只管填写完整性和格式，名称、税号、金额、条款内容不归本项。",
    ),
    Check(
        "pricing", "产品与报价", (_CATALOG, _CALC),
        "用 lookup_product_catalog 取回产品目录，核对第一条、第二条：\n"
        "- 每行 SKU 与产品名称是否和目录一致\n"
        "- 用 calculator 验算：总价 = 单价 × 数量 × 年数，税额 = 总价 × 税率，含税总价 = 总价 + 税额，"
        "合同总价 = 各行含税总价之和，大小写是否一致；每个计算都调用 calculator\n"
        "- 服务等级、增值税发票类型是否二选一勾选；开票金额是否与含税总价一致\n"
        "单价高低、折扣不归本项。",
    ),
    Check(
        "payment", "付款方式", (_PAYMENT, _CALC),
        "用 lookup_payment_terms 取回标准付款条件，核对第三条：\n"
        "- 软件、服务两部分各选了 A 还是 B，比例和付款期限是否与标准一致（期限不得长于标准）\n"
        "- 用 calculator 验算各阶段金额 = 比例 × 对应部分含税总价",
    ),
    Check(
        "floor_price", "价格底线", (_DISCOUNT, _CATALOG, _CALC),
        "用 lookup_discount_rules 取回折扣规则，用 lookup_product_catalog 取回列表价；"
        "按合同 SKU 用 calculator 算折扣率 = 成交单价 ÷ 列表价：\n"
        "- 低于底线登记为 high，建议里写出最低允许单价\n"
        "- 落在需要审批的区间登记为 medium，提示需附审批意见\n"
        "- 高于直签线的不登记\n"
        "只管价格，产品名称、SKU 不归本项。",
    ),
    Check(
        "clauses", "合同条款", (_CLAUSES,),
        "用 lookup_standard_clauses 取回标准条款，逐条对照第五条至第十二条的条款内容：权利义务、保密、知识产权、"
        "违约责任、免责与不可抗力、通知与送达、争议解决、附则。\n"
        "- 对我方更不利的实质改动（违约金、赔偿上限、管辖地等）登记为 high\n"
        "- 份数等程序性差异登记为 low\n"
        "只比条款内容。联系人是否填写、签订地点不归本项。",
    ),
)

_CHECK_PROMPT = """你是栖川软件技术有限公司的合同审核员，负责一份销售合同初审中的「{title}」这一项。我方是合同乙方。

## 本项范围
{instruction}

## 要求
- 依据只能来自工具返回的资料和合同本身，不要编造标准。
- 只登记确实存在的问题；符合要求的不登记，拿不准、需要猜测的不登记。
- 检查完成后调用 submit_check_result 一次，提交本项全部问题；没有问题时传空列表。不要在回复正文里写结果。"""

_SUMMARY_PROMPT = """你是资深公司法务，根据初审登记的问题写审核结论。我方是合同乙方。

- 第一行固定输出：### 审核结论
- 之后用两到三句话说明：这份合同现在能不能签；如果不能，最关键的一两个问题是什么。
- 不要逐条复述问题，不要分级列表，不要写建议清单——问题清单会单独展示。"""

_START = "开始逐项检查：" + "、".join(c.title for c in CHECKS) + "。"
_CANCELLED = "好的，需要初审时把合同发给我就行。"
_NO_RESULT = "⚪ **{title}**：本项没有得出结论"
_PASSED = "✅ **{title}**：未发现问题"
_FOUND = "⚠️ **{title}**：发现 {count} 处问题"
_ALL_PASSED = "### 审核结论\n\n六项检查均未发现问题，可以进入签署流程。"
_DISCLAIMER = "*以上为 AI 初审意见，签署前请交法务复核。*"

_INPUT_TEMPLATE = "# 今天日期\n{today}\n\n# 合同全文\n{contract}"

# 用户消息达到这个长度才当作合同正文，否则弹表单让用户选示例或粘贴
_MIN_CONTRACT_CHARS = 300
_ACTION_START = "start"


def _contract_form() -> AskPayload:
    labels = list(SAMPLES)
    return AskPayload(
        question="请选择一份示例合同，或粘贴要初审的合同正文",
        fields=[
            SelectField(name="sample", label="示例合同", options=labels, default=labels[0]),
            TextField(
                name="text", label="或粘贴合同正文（填写后以这里为准）",
                multiline=True, required=False,
            ),
        ],
        actions=[
            AskAction(id=_ACTION_START, label="开始初审", style="primary"),
            AskAction(id="cancel", label="不审了"),
        ],
    )


def _last_user_text(messages: list[BaseMessage]) -> str:
    last = next((m for m in reversed(messages) if isinstance(m, HumanMessage)), None)
    return last.text.strip() if last else ""


def _submitted(messages: list[BaseMessage]) -> CheckResult | None:
    call = next((
        tc for m in reversed(messages) if isinstance(m, AIMessage)
        for tc in m.tool_calls if tc["name"] == _SUBMIT
    ), None)
    return CheckResult.model_validate(call["args"]) if call else None


def _sorted_issues(raw: list[dict[str, Any]]) -> list[Issue]:
    order = list(_LEVELS)
    return sorted((Issue.model_validate(i) for i in raw), key=lambda i: order.index(i.level))


def _issue_list(issues: list[Issue]) -> str:
    counts = "　".join(
        f"{icon} {label} {n} 处"
        for level, (icon, label) in _LEVELS.items()
        if (n := sum(i.level == level for i in issues))
    )
    items = []
    for n, issue in enumerate(issues, 1):
        icon, _ = _LEVELS[issue.level]
        quote = f"「{issue.quote}」" if issue.quote else "（合同未写明）"
        items.append(
            f"{n}. {icon} **{issue.problem}**\n"
            f"   - 原文：{issue.location}{quote}\n"
            f"   - 建议：{issue.suggestion}"
        )
    return f"### 问题清单\n\n{counts}\n\n" + "\n\n".join(items) + f"\n\n{_DISCLAIMER}"


@register
class ContractReviewTemplate(GraphTemplate):
    """员工给出合同 → 对照工商信息、产品目录、折扣、付款和标准条款逐项检查 → 结论 + 问题清单。"""

    key: ClassVar[str] = "contract_review"
    name: ClassVar[str] = "合同初审"
    description: ClassVar[str] = (
        "签约前自查合同：对照工商信息、产品目录、折扣规则、标准付款条件和标准条款逐项检查，"
        "给出能否签署的结论，以及按严重程度排列的问题、原文位置和修改建议。"
    )
    config_fields: ClassVar[tuple[str, ...] | None] = ("chat_model",)
    category: ClassVar[Literal["general", "business"]] = "business"

    def own_tools(self) -> list[BaseTool]:
        return [
            CompanyLookupTool(),
            ProductCatalogTool(),
            DiscountRulesTool(),
            PaymentTermsTool(),
            StandardClausesTool(),
            CalculatorTool(),
            SubmitCheckResultTool(),
        ]

    def build(
            self,
            *,
            chat_model: BaseChatModel,
            system_prompt: str | None,
            tools: list[BaseTool],
            middleware: list[AgentMiddleware] | None = None,
    ) -> CompiledStateGraph:
        mw = list(middleware or [])
        by_name = {t.name: t for t in tools}

        def check_node(check: Check):
            # internal_step：检查过程的文字不给用户看，工具卡片照常露脸；结果由代码渲染
            reviewer = internal_step(create_agent(
                model=chat_model,
                tools=[by_name[n] for n in (*check.tool_names, _SUBMIT)],
                system_prompt=_CHECK_PROMPT.format(title=check.title, instruction=check.instruction),
                middleware=mw,
            ))

            async def node(state: ReviewState, config: RunnableConfig) -> dict[str, Any]:
                prompt = _INPUT_TEMPLATE.format(today=date.today().isoformat(), contract=state["contract"])
                result = await reviewer.ainvoke({"messages": [HumanMessage(content=prompt)]}, config)
                submitted = _submitted(result["messages"])
                if submitted is None:
                    return {"messages": [emit_text(_NO_RESULT.format(title=check.title))]}
                count = len(submitted.issues)
                line = _FOUND.format(title=check.title, count=count) if count else _PASSED.format(title=check.title)
                return {
                    "issues": [i.model_dump() for i in submitted.issues],
                    "messages": [emit_text(line)],
                }

            return node

        summarizer = create_agent(model=chat_model, tools=[], system_prompt=_SUMMARY_PROMPT, middleware=mw)

        def intake_node(state: ReviewState) -> dict[str, Any]:
            # 函数内 import：runtime 包初始化会 import runner → templates，放顶层成环
            from app.agents.runtime.ask import ask_user

            text = _last_user_text(state["messages"])
            if len(text) < _MIN_CONTRACT_CHARS:
                answer = ask_user(_contract_form())
                if answer.action != _ACTION_START:
                    return {"messages": [emit_text(_CANCELLED)]}
                pasted = str(answer.values.get("text", "")).strip()
                text = pasted or load_sample(str(answer.values.get("sample")))
            return {"contract": text, "messages": [emit_text(_START)]}

        async def summarize_node(state: ReviewState, config: RunnableConfig) -> dict[str, Any]:
            issues = _sorted_issues(state.get("issues", []))
            if not issues:
                return {"messages": [emit_text(_ALL_PASSED)]}
            listing = _issue_list(issues)
            await summarizer.ainvoke({"messages": [HumanMessage(content=listing)]}, config)
            # 结论由模型流式输出在前，清单由代码渲染在后
            return {"messages": [emit_text(listing)]}

        builder = StateGraph(ReviewState)
        builder.add_node("intake", intake_node)
        for check in CHECKS:
            builder.add_node(check.key, check_node(check))
        builder.add_node("summarize", summarize_node)

        builder.add_edge(START, "intake")
        builder.add_conditional_edges(
            "intake", lambda s: CHECKS[0].key if s.get("contract") else END, [CHECKS[0].key, END]
        )
        for current, following in zip(CHECKS, CHECKS[1:]):
            builder.add_edge(current.key, following.key)
        builder.add_edge(CHECKS[-1].key, "summarize")
        builder.add_edge("summarize", END)
        return builder.compile()
