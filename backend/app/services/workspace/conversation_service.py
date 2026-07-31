import logging
from uuid import UUID

from langchain_core.messages import HumanMessage

from app.agents.runtime.runner import build_chat_model
from app.core.exceptions import AppApiException, NotFound404
from app.models import Conversation, User, Workspace
from app.schemas.agent import AgentConfig, ModelParams, ModelSlot
from app.schemas.workspace import (
    ConversationCreate,
    ConversationOut,
    ConversationUpdate,
)

logger = logging.getLogger(__name__)


_TITLE_PROMPT = """请为下面这段用户消息拟一个对话标题。

要求：
- 直接输出标题本身，不要解释、不要引号、不要标点结尾
- 不超过 20 个字，概括这段话在问什么或要做什么
- 与用户消息使用同一种语言

用户消息：
{content}"""

# 起名只看开头 —— 主题几乎总在前面,中间截断对起名没有影响
_TITLE_SOURCE_MAX_CHARS = 500
# Conversation.title 的列宽,兜底截断防 DataError
_TITLE_MAX_CHARS = 150
# 只是防跑飞的闸,不是省钱手段 —— 非推理模型有 prompt 里「不超过 20 字」兜着,
# 给多少都只吐二三十个 token;**推理模型的思考 token 也计在这个额度里**,给少了
# 思考吃光额度、正文一个字都出不来(deepseek-v4-flash 实测:128 全被 reasoning
# 吃掉、finish_reason=length、.text 为空)。所以按能容下思考来给。
_TITLE_MAX_TOKENS = 1024
# 起名要稳定复现,不要发挥
_TITLE_TEMPERATURE = 0.3


def _clean_title(raw: str) -> str:
    """模型输出 → 可入库的标题:压成单行、剥掉包裹的引号、截到列宽。

    prompt 里那句「不要引号」是请求不是保证 —— 模型照样会吐
    `"财报分析"` / `「第三季度财报分析」` / 尾部带换行,这里统一收干净。
    """
    title = " ".join(raw.split())          # 换行 / 连续空白压成单个空格
    title = title.strip("\"'“”‘’「」《》 ")   # 模型爱给标题套引号
    return title[:_TITLE_MAX_CHARS]


class ConversationService:
    """Conversation CRUD。

    URL nested 在 /workspaces/{wid}/conversations/*;
    可见性:用户只能访问自己 workspace 下的 conversation。
    归属校验靠 ORM JOIN 一次过(conversation→workspace→user)。
    """

    async def _ensure_workspace_owned(self, user: User, workspace_id: UUID) -> None:
        """校验 workspace 归属 user(不存在 / 不归属一律返 404)。"""
        exists = await Workspace.filter(id=workspace_id, created_by=user).exists()
        if not exists:
            raise NotFound404("Workspace 不存在")

    async def _get_user_conversation(
        self, user: User, workspace_id: UUID, conversation_id: UUID,
    ) -> Conversation:
        """一次 JOIN 取 conversation + 归属校验。"""
        conv =  await Conversation.filter(
            id=conversation_id,
            workspace_id=workspace_id,
            workspace__created_by=user,
        ).first()
        if conv is None:
            raise NotFound404("Conversation 不存在")
        return conv

    async def create(
        self, user: User, workspace_id: UUID, data: ConversationCreate,
    ) -> ConversationOut:
        """创建对话。先校验 workspace 归属再挂。"""
        await self._ensure_workspace_owned(user, workspace_id)
        conv = await Conversation.create(
            workspace_id=workspace_id,
            title=data.title,
        )
        return ConversationOut.model_validate(conv)

    async def list_in_workspace(
            self, user: User, workspace_id: UUID,
    ) -> list[ConversationOut]:
        """列 workspace 下的对话,按 updated_at 倒序(最近活跃在前)。"""
        await self._ensure_workspace_owned(user, workspace_id)
        convs = await Conversation.filter(workspace_id=workspace_id).order_by("-updated_at")
        return [ConversationOut.model_validate(c) for c in convs]

    async def get_by_id(
            self, user: User, workspace_id: UUID, conversation_id: UUID,
    ) -> ConversationOut:
        conv = await self._get_user_conversation(user, workspace_id, conversation_id)
        return ConversationOut.model_validate(conv)

    async def update(
            self, user: User, workspace_id: UUID, conversation_id: UUID,
            data: ConversationUpdate,
    ) -> ConversationOut:
        conv = await self._get_user_conversation(user, workspace_id, conversation_id)
        if data.title is not None:
            conv.title = data.title
        if data.config is not None:
            conv.config = data.config
        await conv.save()
        return ConversationOut.model_validate(conv)

    async def generate_title(
            self, user: User, workspace_id: UUID, conversation_id: UUID, content: str,
    ) -> str:
        """给对话自动起名(前端在发送消息的同时并发调用)。

        幂等:已有标题就原样返回、不调模型 —— 前端在「发送时」和「进对话时」
        各会触发一次,这里是挡住重复烧钱的唯一一道闸。

        失败不降级:起名失败抛 503、库里保持空字符串。留空下次进对话才会再试;
        写个截断版进去等于把一个平庸标题永久锁死(条件写会挡住后续覆盖)。
        """
        # 一次 JOIN 拿 conversation + 归属校验;select_related 捎上 workspace,
        # 下面要读它的 supervisor jsonb 取模型槽位
        conv = (
            await Conversation.filter(
                id=conversation_id,
                workspace_id=workspace_id,
                workspace__created_by=user,
            )
            .select_related("workspace")
            .first()
        )
        if conv is None:
            raise NotFound404("Conversation 不存在")

        if conv.title:
            return conv.title

        supervisor = AgentConfig.model_validate(conv.workspace.supervisor)
        if supervisor.models.chat is None:
            raise AppApiException(code=503, message="管家还没配对话模型，无法生成标题")

        # 起名单独收窄参数:不继承管家那套 temperature / max_tokens —— 那是给正文
        # 创作用的,起名要短要稳。只借用它的模型 id
        slot = ModelSlot(
            id=supervisor.models.chat.id,
            params=ModelParams(
                temperature=_TITLE_TEMPERATURE, max_tokens=_TITLE_MAX_TOKENS,
            ),
        )

        try:
            model = await build_chat_model(slot)
            prompt = _TITLE_PROMPT.format(content=content[:_TITLE_SOURCE_MAX_CHARS])
            resp = await model.ainvoke([HumanMessage(content=prompt)])
            title = _clean_title(resp.text)
        except Exception as e:
            logger.warning("对话标题生成失败 conversation_id=%s: %s", conversation_id, e)
            raise AppApiException(code=503, message="标题生成失败") from e

        if not title:
            raise AppApiException(code=503, message="标题生成失败")

        # 条件写:只在仍然没名字时落。挡住两件事 —— 并发的第二次生成、
        # 用户在这几秒里手动改了名
        updated = await Conversation.filter(id=conversation_id, title="").update(title=title)
        if updated == 0:
            fresh = await Conversation.filter(id=conversation_id).first()
            return fresh.title if fresh else title

        return title

    async def delete(
            self, user: User, workspace_id: UUID, conversation_id: UUID,
    ) -> None:
        """删 conversation。FK CASCADE 自动连带删 messages。"""
        conv = await self._get_user_conversation(user, workspace_id, conversation_id)
        await conv.delete()


async def get_conversation_service() -> ConversationService:
    return ConversationService()






