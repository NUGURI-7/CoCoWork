"""Workspace 成员（招募进来的 agent 引用）请求/响应 schema。

MemberRecruitIn / MemberOut：API 层契约。
- config（nickname / avatar / 特化 prompt 覆盖）在本层用宽松 dict[str, Any]，
  强类型 schema 留到「派活」那一刀对齐 AgentConfig 范式（API 层宽松、装配层强类型）。
- MemberOut 内嵌 MemberAgentInfo：成员本身只存 agent FK，但前端通讯录要显示
  名字 / 模板，故 service 层 prefetch_related("agent") 后由 Pydantic 递归
  from_attributes 摊出来，避免前端再 N+1 拉 agent 详情。

v1 只做招募 / 列表 / 踢人，不开成员 Update（改覆盖配置留后）。
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class MemberRecruitIn(BaseModel):
    """招募成员请求体：把一个现成 agent 引进当前 workspace。"""

    agent_id: UUID = Field(description="被招募的 agent id（agents 表）")

class MemberAgentInfo(BaseModel):
    """MemberOut 内嵌的 agent 摘要 —— 前端通讯录展示用。"""

    id: UUID
    name: str
    template: str
    avatar_url: str | None = Field(
        default=None,
        description="头像 URL（从 agent.config.ui.avatar_url 摊出，未配为 None）",
    )

    model_config = ConfigDict(from_attributes=True)

class MemberOut(BaseModel):
    """成员对外输出。"""

    id: UUID
    workspace_id: UUID
    agent: MemberAgentInfo
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)





