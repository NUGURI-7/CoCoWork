"""ConversationSummary 数据模型 —— Compress 层 B 的封存产物。

一行 = 一次封存事件:把 covers_until_message(含)之前的对话历史压成一段
中性摘要。append-only:只插入、永不更新,取数用最新一行,旧行留作审计与
压缩效果测量(压缩比曲线直接查表)。

设计要点:
- 中性摘要一份全员共用(所有发言者具名、无第一人称),视角化只发生在
  近段原文的读时改写,与摘要无关
- covers_until_message = 封存游标:摘要覆盖到这条消息(含)为止,之后的
  消息拼上下文时照原样走视角化;消息无单删入口,FK CASCADE 安全
- source_tokens / summary_tokens / trigger = 记账列(Letta compaction_stats
  同款):触发时的上下文水位 / 摘要本身规模 / 触发原因。
  **source_tokens 不是「被封存那段有多长」** —— 它是整个上下文,里面装着系统提示 +
  工具定义 + 花名册这类每轮都在、压缩一个字也动不到的固定开销(实测空对话地板就
  五千多)。拿它除 summary_tokens 算出来的「压缩比」是虚高的。压缩效果看逐轮
  token 曲线(messages 表的 prompt_tokens),这一列的用处是「压缩发生在多高的水位上」
- 链式吸收:二次封存的原料 = 上一行摘要 + 新被封消息,产出新行
- conversation 删则连带删(CASCADE)
"""

from tortoise import fields

from app.models.base import TimestampMixin, UUIDBaseModel


class ConversationSummary(UUIDBaseModel, TimestampMixin):
    """一次封存事件的产物(append-only)。"""

    conversation = fields.ForeignKeyField(
        "models.Conversation", related_name="summaries", on_delete=fields.CASCADE,
    )
    covers_until_message = fields.ForeignKeyField(
        "models.Message", related_name="covering_summaries", on_delete=fields.CASCADE,
        description="封存游标:摘要覆盖到这条消息(含)为止",
    )
    summary_text = fields.TextField(description="中性摘要正文(成品,直接拼进上下文)")

    source_tokens = fields.IntField(
        default=0,
        description="触发时的上下文水位(含固定开销,不是被封存那段的大小)",
    )
    summary_tokens = fields.IntField(default=0, description="摘要正文的 token 数")
    trigger = fields.CharField(
        max_length=32, default="threshold",
        description="触发原因:threshold(超线)/ manual(手动)/ overflow(超窗兜底)",
    )
    model_name = fields.CharField(max_length=100, default="", description="生成摘要用的模型")

    class Meta:
        table = "conversation_summaries"