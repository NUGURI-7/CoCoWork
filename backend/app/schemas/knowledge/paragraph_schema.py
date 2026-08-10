"""Paragraph（文档分段）相关 schema。

只读展示用：一段一条，前端按 `position` 顺序渲染成卡片。
增删改的入参 schema 随「分段编辑」一并加，此处不预留。
"""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, computed_field


class ParagraphOut(BaseModel):
    """段对外输出（分段列表用）。

    `page` 由 `meta` 派生：定位信息在库里是 jsonb（只有 PDF 有页码），对外
    拍平成一个字段——前端不该去认 jsonb 的形状。`meta` 本身 exclude 掉不进
    响应体：它是内部结构，日后往里加键不能变成对外契约。这与 `RetrievalHit`
    的口径一致（那边也是拍平的 `page`）。

    `chunk_count` 不是表上的列，由 service 分页后回填（见 `ParagraphService`）。
    """

    id: UUID
    position: int
    title: str
    content: str
    char_length: int
    chunk_count: int = Field(default=0, description="段内子块数（content 向量数）")

    meta: dict = Field(exclude=True, description="定位信息 jsonb；仅作 page 的来源，不输出")

    @computed_field(description="段的起始页（仅 PDF；其余格式为 null）")
    @property
    def page(self) -> int | None:
        return self.meta.get("page")

    model_config = ConfigDict(from_attributes=True)
