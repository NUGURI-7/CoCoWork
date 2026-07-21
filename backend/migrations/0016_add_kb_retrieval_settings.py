from tortoise import migrations
from tortoise.migrations import operations as ops
from app.models.knowledge import RetrievalMode
from tortoise.fields.base import OnDelete
from tortoise import fields

class Migration(migrations.Migration):
    dependencies = [('models', '0015_add_conversation_summary')]

    initial = False

    operations = [
        ops.AddField(
            model_name='KnowledgeBase',
            name='rerank_model',
            field=fields.ForeignKeyField('models.AIModel', source_field='rerank_model_id', null=True, description='精排模型；空 = 不开 rerank（选了即开，无独立开关）', db_constraint=True, to_field='id', related_name='rerank_knowledge_bases', on_delete=OnDelete.SET_NULL),
        ),
        ops.AddField(
            model_name='KnowledgeBase',
            name='retrieval_mode',
            field=fields.CharEnumField(default=RetrievalMode.VECTOR, description='默认检索模式（KB tool 等无参调用方用；命中测试可请求级覆盖）', db_default='vector', enum_type=RetrievalMode, max_length=20),
        ),
    ]
