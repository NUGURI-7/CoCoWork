from tortoise import migrations
from tortoise.migrations import operations as ops
from tortoise.fields.base import OnDelete
from tortoise import fields

class Migration(migrations.Migration):
    dependencies = [('models', '0029_drop_embedding_kb_index')]

    initial = False

    operations = [
        ops.AlterModelOptions(
            name='KnowledgeBase',
            options={'table': 'knowledge_bases', 'app': 'models', 'pk_attr': 'id', 'table_description': '知识库：一组文档的集合，可在建库时锁定一个 embedding 模型。'},
        ),
        ops.AlterField(
            model_name='KnowledgeBase',
            name='embedding_dim',
            field=fields.IntField(null=True, description='向量维度，随模型锁定'),
        ),
        ops.AlterField(
            model_name='KnowledgeBase',
            name='embedding_model',
            field=fields.ForeignKeyField('models.AIModel', source_field='embedding_model_id', null=True, db_index=True, description='锁定的 embedding 模型', db_constraint=True, to_field='id', related_name='knowledge_bases', on_delete=OnDelete.RESTRICT),
        ),
    ]
