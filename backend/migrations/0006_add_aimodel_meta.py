from tortoise import migrations
from tortoise.migrations import operations as ops
import functools
from json import dumps, loads
from tortoise import fields

class Migration(migrations.Migration):
    dependencies = [('models', '0005_init_knowledge')]

    initial = False

    operations = [
        ops.AddField(
            model_name='AIModel',
            name='meta',
            field=fields.JSONField(null=True, default=dict, description='模型固有事实：dim / context_window / max_input 等（非用户可调）', encoder=functools.partial(dumps, separators=(',', ':')), decoder=loads),
        ),
    ]
