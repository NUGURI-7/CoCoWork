from tortoise import migrations
from tortoise.migrations import operations as ops
from app.models.knowledge import SourceType
from tortoise import fields

class Migration(migrations.Migration):
    dependencies = [('models', '0007_knowledge_enum_status')]

    initial = False

    operations = [
        ops.AlterField(
            model_name='Embedding',
            name='source_type',
            field=fields.CharEnumField(default=SourceType.CONTENT, description='向量来源类型（多向量留口子）', enum_type=SourceType, max_length=20),
        ),
    ]
