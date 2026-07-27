from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ArtifactOut(BaseModel):
    """沙箱产物对外输出 —— 字段与 SSE artifacts 帧一字不差。

    实时那份从 SSE 帧来、回放这份从表里来，两边形状必须相同，
    否则同一个卡片组件要认两种数据。

    **刻意不含 storage_key**：那是服务端内部的存储位置。前端只需要 id，
    点击时拿它换一个短期下载链接（每次都过一遍归属校验）。
    """

    id: UUID
    filename: str
    size: int
    content_type: str

    model_config = ConfigDict(from_attributes=True)

class WorkspaceArtifactItem(ArtifactOut):
    """产出物面板的列表项 —— 在 ArtifactOut 之上加「它是哪来的」。

    继承而非另起：面板点击后走的还是同一个下载接口，公共字段必须一致，
    分成两个平行模型迟早漂移。
    """

    conversation_id: UUID
    conversation_name: str
    message_id: UUID
    created_at: datetime