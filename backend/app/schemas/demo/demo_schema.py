from typing import Literal
from uuid import UUID

from pydantic import BaseModel


class SceneEntryOut(BaseModel):
    """体验场景该跳去哪：单 Agent 给 Agent id，工作空间给访客自己那份的 id。"""

    kind: Literal["agent", "workspace"]
    target_id: UUID


class SceneQuotaOut(BaseModel):
    """当前用户在这个场景今天还能发几条。正式用户不受限，两个字段都为空。"""

    remaining: int | None
    limit: int | None
