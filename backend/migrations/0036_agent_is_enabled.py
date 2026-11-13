from tortoise import migrations
from tortoise.migrations import operations as ops
from tortoise import fields

class Migration(migrations.Migration):
    dependencies = [('models', '0035_conversation_agent_reference')]

    initial = False

    operations = [
        ops.AddField(
            model_name='Agent',
            name='is_enabled',
            field=fields.BooleanField(default=True, description='是否启用。只对管理员建的 Agent 生效：启用则所有人可用，停用则下线', db_default=True),
        ),
    ]
