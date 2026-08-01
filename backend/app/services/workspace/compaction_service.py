"""跨回复历史压缩(Compress 层 B)—— 把越线的旧历史封存成一段中性摘要。

触发判据是 `Conversation.context_tokens`(模型上报的真实 input_tokens),
留多少、切哪儿由 `agents/workspace/history_budget.py` 算,本模块负责
「取原料 → 生成摘要 → 写表」这一段。

三条失败规则(按顺序,第一条没有商量余地):

1. **摘要生成失败绝不落表。** 这张表是 append-only、跨轮复用,而且下一次压缩
   要拿上一条摘要当原料 —— 写进去一条坏摘要,这个对话就永久失忆了,还会被
   下次压缩吸收进去越滚越糟。langchain 的 SummarizationMiddleware 在这里是
   `return f"Error generating summary: {e}"`(把报错字符串当摘要用),它那个位置
   压完一轮就扔所以勉强说得过去,**我们不能抄**。
2. **这一轮降级,用全量历史照常跑完。** 触发线 17 万、窗口 20 万还留着余量,
   刚超线时塞得下。用户已经等了几秒,再让他重发是最差的体验。
3. **全量真的塞不下时机械截断。** 不调模型、丢老留新,零失败风险。
   ——2、3 两条落在调用方(stream 端点),本模块只负责「失败就返回 None」。
"""
import logging
from collections.abc import Sequence
from uuid import UUID

from langchain_core.messages import HumanMessage

from app.agents.runtime.runner import build_chat_model
from app.agents.workspace.history_budget import estimate_text_tokens, find_cutoff
from app.agents.workspace.view_context_assembler import (
    NEUTRAL_VIEW,
    ViewContextAssembler,
    split_at_cursor,
)
from app.models import (
    Conversation,
    ConversationSummary,
    Message,
    Workspace,
    WorkspaceMember,
)
from app.schemas.agent import AgentConfig, ModelParams, ModelSlot
from app.services.sandbox.artifact import group_by_message

logger = logging.getLogger(__name__)


async def latest_summary(conversation_id: UUID) -> ConversationSummary | None:
    """这个对话当前有效的那份摘要 —— 表是 append-only,最新一行即是。

    旧行留着做审计和压缩效果统计(压缩比曲线直接查表),取数只取最新那行。
    两个调用方:压缩时拿它当原料(链式吸收),拼上下文时拿它顶替被封存的历史。
    """
    return await (
        ConversationSummary.filter(conversation_id=conversation_id)
        .order_by("-created_at")
        .first()
    )


_SUMMARY_PROMPT = """你在为一段多人协作的对话做历史归档。这段历史即将被下面你写的
这份摘要**永久替代**,原文不再进入上下文。

## 硬性要求

1. **一律第三人称,所有人具名。绝对不能出现「我」「你」。**
   这份摘要会同时给管家和每一个成员读,「我」指谁会当场错乱。
   人名一律用给出的完整标签(如 `数据分析师#019f0d9b`),不要简写。

2. **只写结论,不写动作。**
   ❌「Supervisor 派活给 数据分析师#019f0d9b 画图 → 完成」
   ✅「数据分析师#019f0d9b 做出了 2024 年销量柱状图,用户要求配色用蓝色系」
   历史里那些「调用了工具 X」的痕迹是给你看的线索,不是要你转述的内容。
   读者需要知道的是**查到了什么、做出了什么**,不是**做过哪些动作**。

3. **不要罗列文件名清单。** 产出的文件由系统另行标注,你只需说清每个产出
   是什么、为什么做。文件名可以顺带提及,但不要试图列全、也不要写文件大小。

4. **总长不超过 1500 字。**

## 输出格式

按下面五节输出。每节都是清单:有内容就写,确实没有就写「无」。

## 用户目标与约束
用户到底想要什么;以及他提过的硬性要求和偏好(用什么不用什么、风格、口径),
这些在后续对话里仍然有效。

## 重要结论
已经查明的事实、已经做出的决定、以及决定背后的理由。包括**被否决的方案和
否决原因** —— 没有这条,后面会有人把已经排除的路再走一遍。

## 各成员的产出
谁交付了什么。按人分条,每条注明是哪一位(完整标签)。
这一节丢了,后面读的人会把别人的成果当成自己的。

## 产出说明
产出的文件分别是什么、为了什么做的。不列清单、不写大小。

## 待办
还有什么没做完。

---

{previous}以下是要归档的对话历史:

{transcript}"""

# 上一份摘要存在时,拼在历史前面一起交给模型(链式吸收)。
# 「可以丢掉过时细节」这句不能省 —— 不说的话模型倾向于把旧摘要原样保留再追加,
# 那就是我们要防的滚雪球
_PREVIOUS_BLOCK = """这是更早以前的历史归档,请把它和下面的新历史合并成一份新的摘要
(合并时可以丢掉其中已经过时、不再影响后续的细节):

{summary}

---

"""

# 摘要不继承管家那套参数(那是给正文创作用的)
_SUMMARY_TEMPERATURE = 0.3   # 归档要稳定复现,不要发挥
_SUMMARY_MAX_TOKENS = 4096   # 防跑飞的闸。**推理模型的思考也吃这个额度** ——
                             # 给少了思考吃光、正文一个字都出不来(起名那处实测过:
                             # 给 128 全被 reasoning 吃掉、返回空串)


class CompactionService:
    """把越线的旧历史封存成一段中性摘要。

    调用方(stream 端点)负责判断该不该压(`history_budget.should_compact`),
    本类负责压得动就压、压不动或压失败就**安静地返回 None** —— 让调用方
    降级用全量历史继续跑,而不是把这一轮拖垮。
    """

    async def compact(
            self,
            conversation: Conversation,
            past: Sequence[Message],
            *,
            trigger: str = "threshold",
    ) -> ConversationSummary | None:
        """压一次。返回新写的摘要行;压不动 / 压失败一律返回 None。

        Args:
            conversation: 需已 prefetch workspace —— 生成摘要用管家的模型,
                要读 `workspace.supervisor` 里的模型槽位。
            past: 这个对话的**全部**历史(按时间升序)。已被上一条摘要覆盖的
                部分由本方法自己扣掉,调用方不必预先筛。
            trigger: 触发原因,可选值见 ConversationSummary.trigger 的说明。
        """
        previous = await latest_summary(conversation.id)

        # 已被上一条摘要覆盖的那半截不能再压一遍(白烧一次调用,而且同一件事会在
        # 新摘要里出现两遍 —— 旧摘要作为原料进去了,原文又进去一次)
        _, uncovered = split_at_cursor(
            past, previous.covers_until_message_id if previous else None
        )
        cutoff = find_cutoff(uncovered)
        if cutoff == 0:
            # 超线了不代表压得动 —— 地板那几千是系统提示和工具定义占的,历史本身
            # 可能就没多长。这时候调模型是纯浪费,还会让它对着一段空原料编一份
            # 摘要写进表。反复打这条日志 = 固定开销本身快撑破窗口了,那是另一个
            # 问题(工具挂太多 / 成员招太多),压缩治不了
            logger.info(
                "跳过压缩:没有可封存的历史 conversation_id=%s 未覆盖=%d 条",
                conversation.id, len(uncovered),
            )
            return None

        material, cursor = uncovered[:cutoff], uncovered[cutoff - 1]

        try:
            transcript = await self._render_material(conversation, material)
            summary_text, model_name = await self._generate(
                conversation.workspace, previous, transcript,
            )
        except Exception as e:
            # **绝不落表**:这张表 append-only、跨轮复用,下次压缩还要拿它当原料。
            # 写进去一条坏摘要,这个对话就永久失忆、还会越滚越糟。
            # 捕获写这么宽是有意的 —— 能炸的东西太杂(超时/限流/模型被删/解析不了),
            # 逐个列会漏,而漏掉的那个正好会让坏数据落表。
            # 返回 None 让调用方降级用全量历史跑完这一轮
            logger.warning(
                "摘要生成失败,本轮降级用全量历史 conversation_id=%s: %s",
                conversation.id, e,
            )
            return None

        if not summary_text:
            # 模型正常返回但吐了个空串(推理模型思考吃光额度就会这样)—— 不是异常、
            # 不会抛。不单独判就会往表里写一行空摘要,**比报错更糟,因为它看起来是成功的**
            logger.warning(
                "摘要生成为空,本轮降级用全量历史 conversation_id=%s", conversation.id,
            )
            return None

        summary = await ConversationSummary.create(
            conversation_id=conversation.id,
            covers_until_message_id=cursor.id,
            summary_text=summary_text,
            source_tokens=conversation.context_tokens,
            summary_tokens=estimate_text_tokens(summary_text),
            trigger=trigger,
            model_name=model_name,
        )
        logger.info(
            "封存历史 conversation_id=%s 封存=%d 条 保留=%d 条 摘要=%d token",
            conversation.id, cutoff, len(uncovered) - cutoff, summary.summary_tokens,
        )
        return summary

    async def _render_material(
            self,
            conversation: Conversation,
            material: Sequence[Message],
    ) -> str:
        """待封存的那段历史 → 一段中性的文本记录(交给摘要模型的原料)。

        **复用 assembler 而不是另写一套渲染**:这样摘要模型看到的,就是这段历史
        本来会被喂进上下文的样子 —— 同一套跳过规则(带 subagent 戳的不回放、
        thinking 不回放)、同一条截断线。另写一套渲染是「两处规则日后跑偏」的
        经典入口。

        NEUTRAL_VIEW 让每一条都走第三人称具名那条路径,一条「我」都不会出现。
        """
        members = await WorkspaceMember.filter(
            workspace_id=conversation.workspace_id
        ).select_related("agent")
        names = {m.id: m.agent.name for m in members}

        context = await ViewContextAssembler().build(
            material, NEUTRAL_VIEW, names, await group_by_message(conversation.id),
            # 取原料时不带摘要：上一份摘要是拼进提示词的（链式吸收），
            # 不该混进这段「要被归档的原文」里
            summary=None,
        )
        # 中性视角下产出的**全是** HumanMessage(没有「我」就没有 AIMessage),
        # 所以直接取正文拼起来即可。不用 langchain 的 get_buffer_string ——
        # 它会给每行加 "Human:" 前缀,而说话人明明已经写在 <msg from> 里了,
        # 两个身份标记打架反而给模型添乱
        return "\n".join(m.text for m in context.messages)

    async def _generate(
            self,
            workspace: Workspace,
            previous: ConversationSummary | None,
            transcript: str,
    ) -> tuple[str, str]:
        """调管家的模型写摘要。返回 (摘要正文, 模型名);正文为空表示没写出来。

        **固定用管家的模型**,不管这一轮是管家还是某个成员在应答 —— 摘要是这个
        对话的公共资产、跨轮反复用,不该跟着「这次碰巧是谁在应答」漂移;成员的
        模型也可能明显弱于管家的,而摘要质量直接决定这个对话往后还记不记得住事。
        """
        cfg = AgentConfig.model_validate(workspace.supervisor)
        if cfg.models.chat is None:
            logger.warning("管家未配 chat 模型,跳过压缩 workspace_id=%s", workspace.id)
            return "", ""

        slot = ModelSlot(
            id=cfg.models.chat.id,
            params=ModelParams(
                temperature=_SUMMARY_TEMPERATURE, max_tokens=_SUMMARY_MAX_TOKENS,
            ),
        )
        prompt = _SUMMARY_PROMPT.format(
            previous=(
                _PREVIOUS_BLOCK.format(summary=previous.summary_text) if previous else ""
            ),
            transcript=transcript,
        )

        model = await build_chat_model(slot)
        resp = await model.ainvoke([HumanMessage(content=prompt)])
        # model_name 切到 100 是列宽兜底(varchar(100)) —— 那个值是从 LangChain
        # 对象上 getattr 摸出来的,不归我们控制,别让一个记账字段把整次压缩的
        # 成果写不进去(同 conversation_service 的 title 截断)
        return resp.text.strip(), getattr(model, "model_name", "")[:100]


async def get_compaction_service() -> CompactionService:
    return CompactionService()
