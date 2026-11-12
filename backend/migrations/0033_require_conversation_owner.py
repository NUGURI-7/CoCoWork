from tortoise import migrations
from tortoise.migrations import operations as ops
from tortoise.fields.base import OnDelete
from tortoise import fields

class Migration(migrations.Migration):
    dependencies = [('models', '0032_backfill_conversation_owner')]

    initial = False

    operations = [
        ops.AlterField(
            model_name='Conversation',
            name='created_by',
            field=fields.ForeignKeyField('models.User', source_field='created_by_id', db_index=True, description='发起人。会话归属以它为准', db_constraint=True, to_field='id', related_name='conversations', on_delete=OnDelete.CASCADE),
        ),
    ]
