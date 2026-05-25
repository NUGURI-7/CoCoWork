from tortoise import migrations
from tortoise.migrations import operations as ops
import functools
from app.db.fields import VectorField
from json import dumps, loads
from tortoise.fields.base import OnDelete
from uuid_utils.compat import uuid7
from tortoise import fields

class Migration(migrations.Migration):
    dependencies = [('models', '0004_add_provider_model_catalog')]

    initial = False

    operations = [
        # 启用 pgvector 扩展（idempotent；本库已启用，本次实际 no-op；
        # 给未来从零部署的库用。回滚时不动它，避免影响其它依赖。）
        ops.RunSQL('CREATE EXTENSION IF NOT EXISTS vector;'),
        ops.CreateModel(
            name='KnowledgeBase',
            fields=[
                ('id', fields.UUIDField(primary_key=True, default=uuid7, unique=True, db_index=True)),
                ('created_at', fields.DatetimeField(description='创建时间', auto_now=False, auto_now_add=True)),
                ('updated_at', fields.DatetimeField(description='更新时间', auto_now=True, auto_now_add=False)),
                ('created_by', fields.ForeignKeyField('models.User', source_field='created_by_id', db_constraint=True, to_field='id', related_name='knowledge_bases', on_delete=OnDelete.CASCADE)),
                ('name', fields.CharField(description='库名', max_length=150)),
                ('description', fields.CharField(default='', description='描述', max_length=500)),
                ('embedding_model', fields.ForeignKeyField('models.AIModel', source_field='embedding_model_id', description='锁定的 embedding 模型', db_constraint=True, to_field='id', related_name='knowledge_bases', on_delete=OnDelete.RESTRICT)),
                ('embedding_dim', fields.IntField(description='向量维度，建库时随模型锁定')),
                ('chunk_config', fields.JSONField(default=dict, description='切块配置：chunk_size / overlap / strategy', encoder=functools.partial(dumps, separators=(',', ':')), decoder=loads)),
                ('status', fields.CharField(default='ready', description='库级状态：ready / reindexing', max_length=20)),
            ],
            options={'table': 'knowledge_bases', 'app': 'models', 'unique_together': (('created_by', 'name'),), 'pk_attr': 'id', 'table_description': '知识库：一组文档的集合，建库时锁定一个 embedding 模型。'},
            bases=['UUIDBaseModel', 'TimestampMixin'],
        ),
        ops.CreateModel(
            name='Document',
            fields=[
                ('id', fields.UUIDField(primary_key=True, default=uuid7, unique=True, db_index=True)),
                ('created_at', fields.DatetimeField(description='创建时间', auto_now=False, auto_now_add=True)),
                ('updated_at', fields.DatetimeField(description='更新时间', auto_now=True, auto_now_add=False)),
                ('knowledge_base', fields.ForeignKeyField('models.KnowledgeBase', source_field='knowledge_base_id', db_constraint=True, to_field='id', related_name='documents', on_delete=OnDelete.CASCADE)),
                ('name', fields.CharField(description='文档名', max_length=255)),
                ('file_type', fields.CharField(description='源文件类型：md / txt', max_length=20)),
                ('size', fields.IntField(default=0, description='字节数')),
                ('storage_key', fields.CharField(description='存储后端的键：S3=对象 key，本地=相对路径', max_length=512)),
                ('char_length', fields.IntField(default=0, description='字符数（冗余展示）')),
                ('paragraph_count', fields.IntField(default=0, description='段数（冗余展示）')),
                ('chunk_count', fields.IntField(default=0, description='子块数 = content 向量数（冗余展示）')),
                ('status', fields.CharField(default='pending', description='pending / processing / completed / failed', max_length=20)),
                ('stage', fields.CharField(default='', description='处理阶段：parsing / splitting / embedding', max_length=20)),
                ('error_message', fields.TextField(default='', description='失败原因', unique=False)),
            ],
            options={'table': 'documents', 'app': 'models', 'pk_attr': 'id', 'table_description': '知识库下的文档。'},
            bases=['UUIDBaseModel', 'TimestampMixin'],
        ),
        ops.CreateModel(
            name='Paragraph',
            fields=[
                ('id', fields.UUIDField(primary_key=True, default=uuid7, unique=True, db_index=True)),
                ('created_at', fields.DatetimeField(description='创建时间', auto_now=False, auto_now_add=True)),
                ('updated_at', fields.DatetimeField(description='更新时间', auto_now=True, auto_now_add=False)),
                ('knowledge_base', fields.ForeignKeyField('models.KnowledgeBase', source_field='knowledge_base_id', db_constraint=True, to_field='id', related_name='paragraphs', on_delete=OnDelete.CASCADE)),
                ('document', fields.ForeignKeyField('models.Document', source_field='document_id', db_constraint=True, to_field='id', related_name='paragraphs', on_delete=OnDelete.CASCADE)),
                ('content', fields.TextField(description='段全文——命中后返回给模型的就是它', unique=False)),
                ('title', fields.CharField(default='', description='段 / 章节标题', max_length=256)),
                ('position', fields.IntField(default=0, description='段在文档中的顺序')),
                ('char_length', fields.IntField(default=0, description='字符数')),
            ],
            options={'table': 'paragraphs', 'app': 'models', 'pk_attr': 'id', 'table_description': '段：展示 / 编辑 / 命中后返回给模型的单元（父子块的父级）。'},
            bases=['UUIDBaseModel', 'TimestampMixin'],
        ),
        ops.CreateModel(
            name='Embedding',
            fields=[
                ('id', fields.UUIDField(primary_key=True, default=uuid7, unique=True, db_index=True)),
                ('knowledge_base', fields.ForeignKeyField('models.KnowledgeBase', source_field='knowledge_base_id', db_constraint=True, to_field='id', related_name='embeddings', on_delete=OnDelete.CASCADE)),
                ('document', fields.ForeignKeyField('models.Document', source_field='document_id', db_constraint=True, to_field='id', related_name='embeddings', on_delete=OnDelete.CASCADE)),
                ('paragraph', fields.ForeignKeyField('models.Paragraph', source_field='paragraph_id', description='始终有——命中后据此返回整段', db_constraint=True, to_field='id', related_name='embeddings', on_delete=OnDelete.CASCADE)),
                ('source_type', fields.CharField(default='content', description='content / question / title', max_length=20)),
                ('text', fields.TextField(description='被 embed 的源文本（content 行 = 子块原文）', unique=False)),
                ('position', fields.IntField(null=True, description='子块在段内顺序（非 content 行可空）')),
                ('embedding', VectorField(description='向量（pgvector，不锁维度）', generated=False, null=False, unique=False)),
                ('meta', fields.JSONField(default=dict, description='元数据', encoder=functools.partial(dumps, separators=(',', ':')), decoder=loads)),
                ('created_at', fields.DatetimeField(description='创建时间', auto_now=False, auto_now_add=True)),
            ],
            options={'table': 'embeddings', 'app': 'models', 'pk_attr': 'id', 'table_description': '向量：embed / 检索单元，一对多指回段（多向量留口子）。'},
            bases=['UUIDBaseModel'],
        ),
    ]
