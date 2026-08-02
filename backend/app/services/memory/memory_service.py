"""常驻记忆的存取层 —— 两个尺度、一次快照、一句话写完。

上层有两条写入路径(用户明说时 LLM 当场调的工具 / 每 N 轮跑一次的后台整理),
它们只负责产出「这一段最新的文字」;落库怎么落、并发撞不撞,全收在本模块。

**写一律走 upsert**:记忆行是 lazy 建的(第一次真要写才存在),而「查一下有没有、
没有就插」在两个对话并发第一次写时会双双查空、双双插入、后到的撞唯一约束。
`ON CONFLICT DO UPDATE` 把判断和写压进一条语句,中间没有缝。后台整理那条路另有
「同工作区只跑一个」的去重键,但 inline 工具那条不经队列、护不到,所以护栏落在这儿。

**读一律按当前登录用户取**,不按 workspace.created_by:今天工作区只有一个归属人,
两种写法结果一样;工作区一旦能共享,前者仍然正确(各人各自那份),后者会让所有人
共用创建者那份。

字数上限是本模块的**最后一道**,不是主约束 —— 主约束在生成侧(整理任务的 prompt
里写死额度)。这里兜的是「模型没听话」,兜法是截断并留 warning,不是静默放行:
放行的代价是每一轮对话都多烧这些字,而且会一直烧下去。
"""
import asyncio
import logging
from dataclasses import dataclass
from uuid import UUID

from app.models import UserMemory, WorkspaceMemory

logger = logging.getLogger(__name__)

# 两个尺度各自的字数上限。用户级更宽,因为它装的是一整份用户画像;工作区级只装
# 本区的偏好与约定,收敛得快。
# 代价要认:用户级那段在**每个**工作区都会被拼进去一次,是「到处都在」的开销,
# 调它等于同时抬高所有工作区每一轮的 prompt 成本。
USER_SCOPE_CHAR_LIMIT = 600
WORKSPACE_SCOPE_CHAR_LIMIT = 400


@dataclass(frozen=True, slots=True)
class MemorySnapshot:
    """一次取数拿到的两段常驻记忆。两段都可能是空串(还没攒出东西)。"""

    user_scope: str = ""       # 全局:这个人是谁,换工作区照样成立
    workspace_scope: str = ""  # 局部:这个人在这个工作区的偏好与约定


def _clamp(content: str, limit: int, scope: str) -> str:
    """超额截断 —— 正常不该触发,触发了说明生成侧的额度约束没生效。"""
    if len(content) <= limit:
        return content
    logger.warning(
        "常驻记忆超额被截断 scope=%s 实际=%d 上限=%d", scope, len(content), limit
    )
    return content[:limit]


class MemoryService:
    """常驻记忆的读写。两条写入路径共用,谁调都走这里。"""

    async def snapshot(
            self, *, user_id: UUID, workspace_id: UUID
    ) -> MemorySnapshot:
        """取这个人在这个工作区下该看到的两段记忆。

        两张表各一次主键级查询,并发发出去 —— 它在每一轮对话的装配路径上,
        能省一个来回就省一个。查不到一律当空串,不区分「没这行」和「有这行
        但没内容」:拼 prompt 时这两种情况的处理完全一样。
        """
        user_row, workspace_row = await asyncio.gather(
            UserMemory.get_or_none(user_id=user_id),
            WorkspaceMemory.get_or_none(workspace_id=workspace_id, user_id=user_id),
        )
        return MemorySnapshot(
            user_scope=user_row.content if user_row else "",
            workspace_scope=workspace_row.content if workspace_row else "",
        )

    async def save_user_scope(self, *, user_id: UUID, content: str) -> None:
        """覆写这个人的全局记忆(没有则建)。"""
        await UserMemory.bulk_create(
            [UserMemory(
                user_id=user_id,
                content=_clamp(content, USER_SCOPE_CHAR_LIMIT, "user"),
            )],
            on_conflict=["user_id"],
            update_fields=["content", "updated_at"],
        )

    async def save_workspace_scope(
            self, *, workspace_id: UUID, user_id: UUID, content: str
    ) -> None:
        """覆写这个人在这个工作区的记忆(没有则建)。"""
        await WorkspaceMemory.bulk_create(
            [WorkspaceMemory(
                workspace_id=workspace_id,
                user_id=user_id,
                content=_clamp(content, WORKSPACE_SCOPE_CHAR_LIMIT, "workspace"),
            )],
            on_conflict=["workspace_id", "user_id"],
            update_fields=["content", "updated_at"],
        )


async def get_memory_service() -> MemoryService:
    return MemoryService()
