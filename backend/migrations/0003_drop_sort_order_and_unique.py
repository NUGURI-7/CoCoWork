from tortoise import migrations
from tortoise.migrations import operations as ops
import functools
from json import dumps, loads
from tortoise import fields

class Migration(migrations.Migration):
    dependencies = [('models', '0002_add_provider_and_ai_model')]

    initial = False

    operations = [
        ops.RemoveConstraint(
            model_name='AIModel',
            name=None,
            fields=['provider', 'model_name'],
        ),
        ops.AlterField(
            model_name='AIModel',
            name='config',
            field=fields.JSONField(default=dict, description='参数预设（temperature / top_p 等）', encoder=functools.partial(dumps, separators=(',', ':')), decoder=loads),
        ),
        ops.RemoveField(model_name='AIModel', name='sort_order'),
        ops.RemoveField(model_name='Provider', name='sort_order'),
    ]
