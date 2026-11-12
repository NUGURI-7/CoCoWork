from tortoise import migrations
from tortoise.migrations import operations as ops
from tortoise.fields.base import OnDelete
from tortoise import fields
from tortoise.migrations.constraints import CheckConstraint

class Migration(migrations.Migration):
    dependencies = [('models', '0034_allow_null_sender_kind')]

    initial = False

    operations = [
        ops.RemoveConstraint(
            model_name='Conversation',
            name='conversations_workspace_xor_agent',
            fields=None,
        ),
        ops.AddField(
            model_name='Conversation',
            name='agent',
            field=fields.ForeignKeyField('models.Agent', source_field='agent_id', null=True, db_index=True, description='独立 Agent 会话填此项；工作空间会话为 NULL', db_constraint=True, to_field='id', related_name='conversations', on_delete=OnDelete.CASCADE),
        ),
        ops.RemoveField(model_name='Conversation', name='agent_key'),
        ops.AddConstraint(
            model_name='Conversation',
            constraint=CheckConstraint(check='num_nonnulls(workspace_id, agent_id) = 1', name='conversations_workspace_xor_agent'),
        ),
    ]
