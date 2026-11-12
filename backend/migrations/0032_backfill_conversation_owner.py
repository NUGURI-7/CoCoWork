from tortoise import migrations
from tortoise.migrations import operations as ops

class Migration(migrations.Migration):
    dependencies = [('models', '0031_conversation_owner_and_agent_key')]

    initial = False

    operations = [
        ops.RunSQL(
            'UPDATE conversations c '
            'SET created_by_id = w.created_by_id '
            'FROM workspaces w '
            'WHERE w.id = c.workspace_id AND c.created_by_id IS NULL;',
            reverse_sql='',
        ),
    ]
