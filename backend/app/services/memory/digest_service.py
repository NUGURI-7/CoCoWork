"""记忆整理 —— 后台从最近的用户发言里沉淀常驻记忆。

**输入只喂用户说过的话**,助手的发言一条都不进来。这条规矩不写在 prompt 里
靠模型自觉,而是从取数就切掉:模型对用户的推测(「看起来你更喜欢简洁的回答」)
本来就长在助手消息里,输入里没有它,就无从把猜测写成事实。

**不设游标**,每次读最近这几条用户发言,读重了也不管。因为产出是两格的完整
新版本、且已有记忆一并喂进去 —— 同一句话被读第二遍,吐出来的还是同一段文字,
比对下来没变就不写库。重复是自愈的,为它维护一个游标不划算。

**失败绝不落库**(同 compaction_service 的第一条规矩):解析失败、模型抽风、
超时,一律当作「这次没整理出东西」,保持原样。记忆是跨会话长期复用的,写进去
一段坏内容,它会一直影响之后每一轮对话,而且没人会去核对。
"""
import logging
from uuid import UUID

from langchain_core.messages import HumanMessage
from pydantic import BaseModel, ValidationError

from app.agents.runtime.blocks import TextBlock, parse_blocks
from app.agents.runtime.runner import build_chat_model
from app.models import Conversation, Message, MessageRole
from app.schemas.agent import AgentConfig, ModelParams, ModelSlot
from app.services.memory.memory_service import (
    USER_SCOPE_CHAR_LIMIT,
    WORKSPACE_SCOPE_CHAR_LIMIT,
    MemoryService,
)

logger = logging.getLogger(__name__)

# 读最近多少条用户发言。取得比触发间隔宽一些,让相邻两次整理有重叠 ——
# 卡在边界上的那句话不会因为「上次没轮到、这次已翻篇」而两头落空
_DIGEST_WINDOW = 20
# 整理要稳定复现,不要发挥。取 0.1 是跟 mem0 的默认值对齐(它做的是同一件事:
# 从对话里抽事实再决定怎么更新记忆),不是拍脑袋定的
_DIGEST_TEMPERATURE = 0.1
# 两格加起来一千字,JSON 转义和推理模型的思考 token 都算在这个额度里
_DIGEST_MAX_TOKENS = 2048

# 每多少条用户发言整理一次。比 Letta sleep-time agent 的默认值(每 5 步)稀一倍 ——
# 整理一次就是一次模型调用,而记忆是收敛的,跑太勤大多数轮次都白跑。
# **必须小于 _DIGEST_WINDOW**:窗口 20 条、间隔 10 条,相邻两次整理有一倍重叠,
# 卡在边界上的那句话不会因为「上次没轮到、这次已翻篇」而两头落空
DIGEST_EVERY_N_USER_MESSAGES = 10

_DIGEST_PROMPT = """你在帮一位用户维护他的长期记忆。下面是他最近说过的话,判断里面有没有值得长期记住的东西。

## 记忆分两格,主语都是这位用户

全局:这个人本身的情况,他在哪个工作空间都成立。例:「做后端开发」「回答一律用中文」
本空间:他在当前这个工作空间里的做法,只在这里成立。例:「金额保留两位小数」「图表用横向柱状图」

本空间那格记的是**他自己**的做法,不是整个工作空间公用的规章。别写成「本项目统一要求…」。

## 三条标准,全部满足才记

1. 下次还成立。「这个文件叫 a.csv」下一轮就没用了,不记;「我做后端」下个月还成立,记。
2. 反复出现过。只说过一次的不记;同一件事出现两三次,或者他明说「我一直都这样」「以后都这样」,才记。
3. 说得具体。「喜欢简洁」太虚,写进去也没用;「回答控制在三段以内」才照着做得了。

## 拿不准记哪一格,一律记本空间

记错到本空间,他换个工作空间再说一遍就行。记错到全局,这条规矩会跟着他进**所有**工作空间,
而他根本不知道新开的空间为什么莫名其妙要求金额两位小数 —— 那是查不出来的毛病。
要进全局,得是他自己明说过「我一直都这样」这类话。

本空间那格里已经记着的内容,如果有哪条其实换个工作空间也成立、而且他明说过,
把它挪进全局并从本空间删掉,不要两格都留着。

## 已有的记忆

全局(上限 {user_limit} 字):
{user_memory}

本空间(上限 {workspace_limit} 字):
{workspace_memory}

## 他最近说的话

{recent}

## 输出

只输出一个 JSON,不要解释、不要代码块围栏:
{{"user": "全局那格的完整新内容", "workspace": "本空间那格的完整新内容"}}

两格都要给**完整新版本**,不是增量 —— 没变化的那格把原文原样抄回来。
一条一句话,用他自己读得懂的说法:这些字会原样展示给他看,
别写「用户偏好于」「系统应当」这种腔调。
这次没沉淀出新东西,就把两格原文都原样抄回来。大部分对话都记不出东西,这很正常。"""


class _DigestOutput(BaseModel):
    """模型吐回来的两格新内容。"""

    user: str = ""
    workspace: str = ""


def _say(message: Message) -> str:
    """一条库里的消息 → 它的纯文本正文。

    **走 parse_blocks 而不是 runner.content_to_text**:那个函数是给请求路径用的,
    它按 `isinstance(b, TextBlock)` 挑块,而请求里的块是 Pydantic 对象;
    库里 `content` 是 jsonb 存下来的 **dict 列表**,isinstance 一个都匹配不上 ——
    不报错,静默返回空串,原料就全喂空了(实测踩过)。DB 那条路一律先 parse_blocks。
    """
    return "".join(
        b.text for b in parse_blocks(message.content) if isinstance(b, TextBlock)
    ).strip()


def _parse(raw: str) -> _DigestOutput | None:
    """抠出 JSON —— prompt 里那句「不要围栏」是请求不是保证。

    「围栏」= markdown 的三个反引号。模型很爱把 JSON 包成 ```json {…} ``` 交回来,
    直接丢给解析器会被反引号噎住,这里先把那层壳剥掉。
    """
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1].rsplit("```", 1)[0]
    try:
        return _DigestOutput.model_validate_json(text)
    except ValidationError:
        logger.warning("记忆整理输出不是预期的 JSON: %r", raw[:200])
        return None


class MemoryDigestService:
    """跑一次记忆整理。产出两格的完整新版本,只把变了的那格落库。"""

    async def run(self, conversation_id: UUID) -> bool:
        """整理一次。真写了库返回 True;没得写、或任何一步失败返回 False。

        入参只收 id 而不是 ORM 对象 —— 它下一步要变成队列任务,参数得是 JSON
        装得下的东西。
        """
        conv = (
            await Conversation.filter(id=conversation_id)
            .select_related("workspace")
            .first()
        )
        if conv is None:
            return False

        workspace = conv.workspace
        user_id = workspace.created_by_id

        rows = (
            await Message.filter(
                conversation_id=conversation_id, role=MessageRole.USER
            )
            .order_by("-created_at")
            .limit(_DIGEST_WINDOW)
        )
        # 查出来是倒序(要的是最近那几条),喂给模型得正着来。
        # 空正文的消息(只拖了个附件、没打字)直接丢掉,它对整理没有信息量
        said = [text for m in reversed(rows) if (text := _say(m))]
        if not said:
            return False
        recent = "\n".join(f"- {text}" for text in said)

        svc = MemoryService()
        memory = await svc.snapshot(user_id=user_id, workspace_id=workspace.id)

        supervisor = AgentConfig.model_validate(workspace.supervisor)
        if supervisor.models.chat is None:
            return False

        # 同起名那条路:只借管家的模型 id,参数另给一套 —— 管家那套是给正文创作
        # 调的,整理要的是稳定复现
        slot = ModelSlot(
            id=supervisor.models.chat.id,
            params=ModelParams(
                temperature=_DIGEST_TEMPERATURE, max_tokens=_DIGEST_MAX_TOKENS
            ),
        )

        try:
            model = await build_chat_model(slot)
            prompt = _DIGEST_PROMPT.format(
                user_limit=USER_SCOPE_CHAR_LIMIT,
                workspace_limit=WORKSPACE_SCOPE_CHAR_LIMIT,
                user_memory=memory.user_scope or "(空)",
                workspace_memory=memory.workspace_scope or "(空)",
                recent=recent,
            )
            resp = await model.ainvoke([HumanMessage(content=prompt)])
        except Exception as exc:
            logger.warning(
                "记忆整理调模型失败 conversation_id=%s: %s", conversation_id, exc
            )
            return False

        out = _parse(resp.text)
        if out is None:
            return False

        # **只写变了的那格**。理由不是省这一次写库,是保住 updated_at 的真实性:
        # 它是唯一能回答「这段记忆是什么时候定下来的」的字段,每次整理都刷一遍,
        # 它就永远显示「几分钟前」,这一列等于废了。返回的 changed 同理 ——
        # 「整理跑了 20 次、有几次真沉淀出东西」只能靠它统计
        changed = False
        if out.workspace != memory.workspace_scope:
            await svc.save_workspace_scope(
                workspace_id=workspace.id, user_id=user_id, content=out.workspace
            )
            changed = True
        if out.user != memory.user_scope:
            await svc.save_user_scope(user_id=user_id, content=out.user)
            changed = True

        if changed:
            logger.info(
                "记忆已更新 conversation_id=%s workspace=%d字 user=%d字",
                conversation_id, len(out.workspace), len(out.user),
            )
        return changed


async def should_digest(conversation_id: UUID) -> bool:
    """这一轮结束后该不该整理 —— 按这个对话的用户发言条数整除判定。

    **刻意不加计数列**:这个判断本来就不需要精确。偶尔多跑一次、或者晚几轮才跑,
    代价只是多一次模型调用 / 晚几轮沉淀,为它加一列 + 一次迁移换不回来。
    开销也不值一提:按 conversation_id 走索引取回这个对话的消息再筛 role,
    一个对话就几十条。
    """
    said = await Message.filter(
        conversation_id=conversation_id, role=MessageRole.USER
    ).count()
    return said > 0 and said % DIGEST_EVERY_N_USER_MESSAGES == 0


async def get_memory_digest_service() -> MemoryDigestService:
    return MemoryDigestService()
