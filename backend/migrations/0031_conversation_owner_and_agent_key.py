from tortoise import migrations
from tortoise.migrations import operations as ops
from tortoise.fields.base import OnDelete
from tortoise import fields
from tortoise.migrations.constraints import CheckConstraint

class Migration(migrations.Migration):
    dependencies = [('models', '0030_allow_keyword_only_knowledge_base')]

    initial = False

    operations = [
        ops.AlterModelOptions(
            name='Conversation',
            options={'table': 'conversations', 'app': 'models', 'constraints': [CheckConstraint(check='num_nonnulls(workspace_id, agent_key) = 1', name='conversations_workspace_xor_agent')], 'pk_attr': 'id', 'table_description': '一条对话流：属于某个工作空间，或属于某个独立 Agent，二者必居其一。'},
        ),
        ops.AlterField(
            model_name='Conversation',
            name='workspace',
            field=fields.ForeignKeyField('models.Workspace', source_field='workspace_id', null=True, description='工作空间会话填此项；独立 Agent 会话为 NULL', db_constraint=True, to_field='id', related_name='conversations', on_delete=OnDelete.CASCADE),
        ),
        ops.AddField(
            model_name='Conversation',
            name='agent_key',
            field=fields.CharField(null=True, description='独立 Agent 会话填该 Agent 在代码里的固定标识；工作空间会话为 NULL', max_length=64),
        ),
        ops.AddField(
            model_name='Conversation',
            name='created_by',
            field=fields.ForeignKeyField('models.User', source_field='created_by_id', null=True, db_index=True, description='发起人。会话归属以它为准', db_constraint=True, to_field='id', related_name='conversations', on_delete=OnDelete.CASCADE),
        ),
        ops.AddConstraint(
            model_name='Conversation',
            constraint=CheckConstraint(check='num_nonnulls(workspace_id, agent_key) = 1', name='conversations_workspace_xor_agent'),
        ),
    ]
