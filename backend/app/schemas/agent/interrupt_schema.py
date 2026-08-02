"""HITL 中断的数据格式 —— 停下来时发什么、用户答完回什么。

一个结构覆盖全部场景，不为「确认」「填表」分类型：
- 危险操作确认 = 零字段 + 两个按钮
- 派活选人     = 一个 select + 确认/取消
- 缺信息追问   = 若干 text + 一个提交

字段类型用判别联合而非「一个类塞 type」：只有 select 系有 options，
文本框根本不存在这个字段，填错在校验期就报错（同 ContentBlock 的路子）。
往后加类型（日期、文件…）只是多一个类，不动已有的四个。
"""

from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.workspace.message_model import SenderKind


class _AskFieldBase(BaseModel):
    """四种字段的共有部分。"""

    name: str = Field(description="变量名 —— 用户填的值按它回传")
    label: str = Field(description="显示名 —— 给人看的那行字")
    required: bool = True


class TextField(_AskFieldBase):
    """文本输入。带 default 即「让用户改一改模型写好的东西」，
    不必为『审阅并编辑』另立一种类型。"""

    type: Literal["text"] = "text"
    default: str | None = None
    multiline: bool = False


class SelectField(_AskFieldBase):
    """单选。

    选项在发起中断时就算好 —— 不支持运行时再去取值，那是给「用户自己搭
    工作流」用的能力，本项目没有画布。

    allow_custom 覆盖「三个选项都不满意，我自己说一个」：真实产品里这是
    一个字段而非两个（选项 + 另一个输入框），免得出现「既选了 A 又填了别的」
    这种没法解释的组合。
    """

    type: Literal["select"] = "select"
    options: list[str] = Field(min_length=1, description="至少一项，空选项框没有意义")
    default: str | None = None
    allow_custom: bool = False


class MultiSelectField(_AskFieldBase):
    """多选 —— 八个选项里挑三个那种。

    单独立类而不是给 SelectField 加个 multiple 开关：那样同一个字段的回传值
    会时而是字符串、时而是列表，前后端都得先判断再取。分开之后类型是确定的。
    """

    type: Literal["multi_select"] = "multi_select"
    options: list[str] = Field(min_length=1)
    default: list[str] = Field(default_factory=list)
    allow_custom: bool = False


class BooleanField(_AskFieldBase):
    """勾选框。"""

    type: Literal["boolean"] = "boolean"
    default: bool = False


# 判别联合：靠 type 值分派到具体类，Pydantic 据此校验各自的必填项
AskField = Annotated[
    TextField | SelectField | MultiSelectField | BooleanField,
    Field(discriminator="type"),
]


class AskAction(BaseModel):
    """一个按钮。

    danger 这档是从 Dify 的坑里直接捡的便宜 —— 它的按钮样式表里没有
    「危险」，模型想要个红色的确认删除只能降级成别的色，还得写注释解释。
    """

    id: str = Field(description="回传时用它标识用户点了哪个")
    label: str
    style: Literal["default", "primary", "danger"] = "default"


def _default_actions() -> list[AskAction]:
    """没给按钮时的兜底 —— 一个表单总得有地方可以交。"""
    return [AskAction(id="submit", label="提交", style="primary")]


class AskPayload(BaseModel):
    """停下来时发给前端的东西 —— 即 interrupt() 的载荷。"""

    question: str = Field(description="为什么停下来，一句话")
    fields: list[AskField] = Field(default_factory=list)
    actions: list[AskAction] = Field(default_factory=_default_actions)

    # 谁在问 —— 与 messages 表的 sender_kind / sender_member_id 同构。
    # 群聊里前端要据此显示「张三在问你」，而不是笼统的「AI 在问你」；
    # supervisor 发问时 member_id 为空，与消息落库时的处理一致
    asker_kind: SenderKind = SenderKind.SUPERVISOR
    asker_name: str = ""
    asker_member_id: UUID | None = None


class AskAnswer(BaseModel):
    """用户提交回来的东西 —— 即 Command(resume=...) 的载荷。

    values 的键是 AskField.name，值的形状随字段类型而定：
    text / select 回字符串，multi_select 回字符串列表，boolean 回真假。
    """

    action: str = Field(description="点了哪个按钮的 id")
    values: dict[str, str | bool | list[str]] = Field(default_factory=dict)
