from tortoise import migrations
from tortoise.migrations import operations as ops
from tortoise.fields.base import OnDelete
from tortoise import fields

class Migration(migrations.Migration):
    dependencies = [('models', '0028_skill_unique_name')]

    initial = False

    operations = [
        ops.AlterField(
            model_name='Embedding',
            name='knowledge_base',
            field=fields.ForeignKeyField('models.KnowledgeBase', source_field='knowledge_base_id', db_constraint=True, to_field='id', related_name='embeddings', on_delete=OnDelete.CASCADE),
        ),
    ]
