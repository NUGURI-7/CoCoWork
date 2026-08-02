from tortoise import migrations
from tortoise.migrations import operations as ops
from app.models.workspace.message_model import MessageStatus
from tortoise import fields

class Migration(migrations.Migration):
    dependencies = [('models', '0026_add_memory_tables')]

    initial = False

    operations = [
        ops.AlterField(
            model_name='Message',
            name='status',
            field=fields.CharEnumField(default=MessageStatus.DONE, description='done/error/stopped/interrupted(流式中不入库；interrupted 非终态)', enum_type=MessageStatus, max_length=16),
        ),
    ]
