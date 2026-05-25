"""知识库 / RAG 数据模型。

一簇紧耦合的模型放同一文件：KnowledgeBase / Document / Paragraph / Embedding。
层级：文档 → 段(Paragraph) → 子块（不落表，文本存 Embedding.text）。
"""

from tortoise import fields

from app.db.fields import VectorField
from app.models.base import TimestampMixin, UUIDBaseModel


class KnowledgeBase(UUIDBaseModel, TimestampMixin):
    """知识库：一组文档的集合，建库时锁定一个 embedding 模型。

    - `embedding_model` / `embedding_dim`：锁定的向量化模型与维度（换模型 = 全库重建）
    - `chunk_config`：库级切块配置（chunk_size / overlap / strategy），改了需重切
    - `status`：库级状态（ready / reindexing，给换模型重建用）
    """

    created_by = fields.ForeignKeyField(
        "models.User", related_name="knowledge_bases", on_delete=fields.CASCADE,
    )
    name = fields.CharField(max_length=150, description="库名")
    description = fields.CharField(max_length=500, default="", description="描述")
    embedding_model = fields.ForeignKeyField(
        "models.AIModel", related_name="knowledge_bases", on_delete=fields.RESTRICT,
        description="锁定的 embedding 模型",
    )
    embedding_dim = fields.IntField(description="向量维度，建库时随模型锁定")
    chunk_config = fields.JSONField(default=dict, description="切块配置：chunk_size / overlap / strategy")
    status = fields.CharField(max_length=20, default="ready", description="库级状态：ready / reindexing")

    class Meta:
        table = "knowledge_bases"
        unique_together = (("created_by", "name"),)


class Document(UUIDBaseModel, TimestampMixin):
    """知识库下的文档。

    原文件存对象存储（`storage_key` 指向）；文本解析、切段、切块、向量化后
    分别落到 Paragraph / Embedding。`status` + `stage` + `error_message`
    跟踪异步处理管线。v1 手动向量化：上传只建记录（status=pending）。
    """

    knowledge_base = fields.ForeignKeyField(
        "models.KnowledgeBase", related_name="documents", on_delete=fields.CASCADE,
    )
    name = fields.CharField(max_length=255, description="文档名")
    file_type = fields.CharField(max_length=20, description="源文件类型：md / txt")
    size = fields.IntField(default=0, description="字节数")
    storage_key = fields.CharField(
        max_length=512, description="存储后端的键：S3=对象 key，本地=相对路径",
    )
    char_length = fields.IntField(default=0, description="字符数（冗余展示）")
    paragraph_count = fields.IntField(default=0, description="段数（冗余展示）")
    chunk_count = fields.IntField(default=0, description="子块数 = content 向量数（冗余展示）")
    status = fields.CharField(
        max_length=20, default="pending",
        description="pending / processing / completed / failed",
    )
    stage = fields.CharField(
        max_length=20, default="", description="处理阶段：parsing / splitting / embedding",
    )
    error_message = fields.TextField(default="", description="失败原因")

    class Meta:
        table = "documents"


class Paragraph(UUIDBaseModel, TimestampMixin):
    """段：展示 / 编辑 / 命中后返回给模型的单元（父子块的父级）。

    `content` 是命中后返回给模型的整段文本；段内再切成子块去 embed
    （子块不落表，文本存 Embedding.text）。
    """

    knowledge_base = fields.ForeignKeyField(
        "models.KnowledgeBase", related_name="paragraphs", on_delete=fields.CASCADE,
    )
    document = fields.ForeignKeyField(
        "models.Document", related_name="paragraphs", on_delete=fields.CASCADE,
    )
    content = fields.TextField(description="段全文——命中后返回给模型的就是它")
    title = fields.CharField(max_length=256, default="", description="段 / 章节标题")
    position = fields.IntField(default=0, description="段在文档中的顺序")
    char_length = fields.IntField(default=0, description="字符数")

    class Meta:
        table = "paragraphs"


class Embedding(UUIDBaseModel):
    """向量：embed / 检索单元，一对多指回段（多向量留口子）。

    - 始终挂 `paragraph`：命中后据此返回整段（父子块）。
    - `source_type`：content（v1 唯一）/ question / title。
    - `text`：被 embed 的源文本（content 行 = 子块原文）。
    - `embedding`：pgvector 向量，列不锁维度（兼容多库不同维度）。
    - 不可变派生数据（重嵌入 = 删了重建），故只有 `created_at`、无 `updated_at`。
    """

    knowledge_base = fields.ForeignKeyField(
        "models.KnowledgeBase", related_name="embeddings", on_delete=fields.CASCADE,
    )
    document = fields.ForeignKeyField(
        "models.Document", related_name="embeddings", on_delete=fields.CASCADE,
    )
    paragraph = fields.ForeignKeyField(
        "models.Paragraph", related_name="embeddings", on_delete=fields.CASCADE,
        description="始终有——命中后据此返回整段",
    )
    source_type = fields.CharField(
        max_length=20, default="content", description="content / question / title",
    )
    text = fields.TextField(description="被 embed 的源文本（content 行 = 子块原文）")
    position = fields.IntField(null=True, description="子块在段内顺序（非 content 行可空）")
    embedding = VectorField(description="向量（pgvector，不锁维度）")
    meta = fields.JSONField(default=dict, description="元数据")
    created_at = fields.DatetimeField(auto_now_add=True, description="创建时间")

    class Meta:
        table = "embeddings"
