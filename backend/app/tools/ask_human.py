"""向用户提问 —— 模型主动发起的人工介入。

与「工具审批」那一路的区别：这是模型**自己判断拿不准**时开口问，不是系统
硬拦。所以它是一个挂给模型的工具，而不是拦在工具执行前的中间件。

一次调用可以问多个问题，翻译成**一次**中断 —— 用户在同一张表单里一并作答、
一次恢复。实测下来中断是一个一个来的（图撞上第一个就整体冻住，后面的工具
压根没执行），所以「多个问题」只能靠一次调用里多带几个字段来表达，靠模型
连着调几次只会让用户被追问好几轮。

模型侧参数仍比 AskPayload 简单（问题 + 选项 + 能否多选）：让模型去填四种
字段类型、按钮样式那整套结构，错得多、收益小。这一层只做翻译。
"""

from uuid import UUID

from pydantic import BaseModel, Field

from app.agents.runtime.ask import ask_user
from app.models.workspace.message_model import SenderKind
from app.schemas.agent.interrupt_schema import (
    AskAction,
    AskAnswer,
    AskField,
    AskPayload,
    MultiSelectField,
    SelectField,
    TextField,
)
from app.tools.base import CoCoTool

_DESCRIPTION = """向用户提问，拿到必要的信息或决定后再继续。

只在答案无法从对话、上下文或其他工具推断出来时才用 —— 自己查得到的别问，
问了也无所谓的细节别问。

该问的两种情况：几个做法都合理、选哪个取决于用户偏好；缺关键信息且猜错代价大。

一次调用可以问多个问题 —— 相关的问题请一次问完，用户在同一张表单里一并作答，
不要拆成好几轮来回追问。

每个问题的 options 留空 = 让用户自由填写；给了 options = 让他从中挑
（他仍然可以自己写一个）。"""

_ACTION_SUBMIT = "submit"
_ACTION_CANCEL = "cancel"

# 多个问题时的表单标题 —— 单个问题时标题就是那句问话本身，不用这个
_MULTI_TITLE = "有几件事需要你确认："


class AskItem(BaseModel):
    """一个问题。"""

    question: str = Field(description="要问的那句话，直接、具体")
    options: list[str] = Field(
        default_factory=list, description="可选项；留空则让用户自由输入"
    )
    multiple: bool = Field(
        default=False, description="能否多选；仅在给了 options 时有意义"
    )


class AskHumanInput(BaseModel):
    questions: list[AskItem] = Field(
        min_length=1,
        description="要问的问题，相关的一次问完 —— 用户在同一张表单里一并作答",
    )


def _field_name(index: int) -> str:
    """字段名按序号排，与 questions 一一对应 —— 回答按它取回。"""
    return f"q{index}"


def _build_field(name: str, label: str, item: AskItem) -> AskField:
    """一个问题 → 一个字段。

    allow_custom 恒为真：多给用户一个「都不合适、我自己说」的口子几乎总是
    对的，不必让模型操心这件事。
    """
    if not item.options:
        return TextField(name=name, label=label)
    if item.multiple:
        return MultiSelectField(
            name=name, label=label, options=item.options, allow_custom=True
        )
    return SelectField(
        name=name, label=label, options=item.options, allow_custom=True
    )


def _build_form(items: list[AskItem]) -> tuple[str, list[AskField]]:
    """问题列表 → (表单标题, 字段列表)。

    单个问题时标题就是那句问话、字段标签用泛称；多个问题时标题退成一句引导语、
    每个字段的标签才是各自的问题 —— 免得同一句话在界面上出现两遍。
    """
    if len(items) == 1:
        return items[0].question, [_build_field(_field_name(0), "你的回答", items[0])]

    fields = [
        _build_field(_field_name(i), it.question, it) for i, it in enumerate(items)
    ]
    return _MULTI_TITLE, fields


def _one_value(answer: AskAnswer, index: int) -> str:
    """取第 index 个问题的答案，多选拼成一句。"""
    value = answer.values.get(_field_name(index))
    if isinstance(value, list):
        return "、".join(value)
    return value if isinstance(value, str) else ""


def _render(answer: AskAnswer, items: list[AskItem]) -> str:
    """用户的回答 → 给模型看的一段话。

    「跳过」和前端叉掉表单是同一件事，都走 cancel 这一支 —— 用户的意思都是
    「这个我不答」，没必要在协议里分成两种。真要中止整轮回复，走的是现有的
    停止生成那条路，与这里无关。
    """
    if answer.action == _ACTION_CANCEL:
        # 措辞要断掉模型「再问一遍」的念想，否则会问→跳过→又问，原地打转。
        # 同 LangChain 官方 reject 分支的口径（它也明说 do not retry）
        return (
            "用户跳过了这些问题，没有作答。不要重复追问同一件事 —— "
            "按合理的默认继续，或者在回复里说明你还缺什么。"
        )

    if len(items) == 1:
        value = _one_value(answer, 0)
        return f"用户回答：{value}" if value else "用户提交了，但没有填写内容。"

    lines = [
        f"- {it.question} {_one_value(answer, i) or '（未填）'}"
        for i, it in enumerate(items)
    ]
    return "用户回答：\n" + "\n".join(lines)


class AskHumanTool(CoCoTool):
    """问用户几句，等答案回来再继续。"""

    name: str = "ask_human"
    display_name: str = "询问用户"
    description: str = _DESCRIPTION
    args_schema: type[BaseModel] = AskHumanInput

    # ---- per-run bound：构造时绑定「谁在问」，模型无从伪造 ----
    # 群聊里前端要据此显示「张三在问你」而不是笼统的「AI 在问你」
    asker_kind: SenderKind = SenderKind.SUPERVISOR
    asker_name: str = ""
    asker_member_id: UUID | None = None

    async def _execute(self, questions: list[AskItem]) -> str:
        # LangChain 按 args_schema 解析后注入的是已校验的模型对象，但 MCP /
        # 直接构造等路径可能塞进裸 dict，统一收口一次再用
        items = [AskItem.model_validate(q) for q in questions]
        title, fields = _build_form(items)

        answer = ask_user(
            AskPayload(
                question=title,
                fields=fields,
                actions=[
                    AskAction(id=_ACTION_SUBMIT, label="提交", style="primary"),
                    AskAction(id=_ACTION_CANCEL, label="跳过"),
                ],
                asker_kind=self.asker_kind,
                asker_name=self.asker_name,
                asker_member_id=self.asker_member_id,
            )
        )
        return _render(answer, items)
