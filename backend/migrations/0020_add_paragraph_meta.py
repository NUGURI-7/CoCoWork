from tortoise import migrations
from tortoise.migrations import operations as ops
from orjson import loads
from tortoise.fields.data import JSON_DUMPS
from tortoise import fields

class Migration(migrations.Migration):
    dependencies = [('models', '0019_add_sandbox_artifact')]

    initial = False

    operations = [
        ops.AddField(
            model_name='Paragraph',
            name='meta',
            field=fields.JSONField(default=dict, description="定位信息等元数据：PDF 存 {'page': 12}（段的起始页），其余格式为空", db_default='{}', encoder=JSON_DUMPS, decoder=loads),
        ),
    ]
