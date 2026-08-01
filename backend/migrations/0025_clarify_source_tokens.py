from tortoise import migrations
from tortoise.migrations import operations as ops
from tortoise import fields

class Migration(migrations.Migration):
    dependencies = [('models', '0024_add_message_token_usage')]

    initial = False

    operations = [
        ops.AlterField(
            model_name='ConversationSummary',
            name='source_tokens',
            field=fields.IntField(default=0, description='触发时的上下文水位(含固定开销,不是被封存那段的大小)'),
        ),
    ]
