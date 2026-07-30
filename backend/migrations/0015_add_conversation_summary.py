from tortoise import migrations
from tortoise.migrations import operations as ops
from tortoise.fields.base import OnDelete
from uuid_utils.compat import uuid7
from tortoise import fields

class Migration(migrations.Migration):
    dependencies = [('models', '0014_add_paragraph_search_vector_gin')]

    initial = False

    operations = [
        ops.CreateModel(
            name='ConversationSummary',
            fields=[
                ('id', fields.UUIDField(primary_key=True, default=uuid7, unique=True, db_index=True)),
                ('created_at', fields.DatetimeField(description='创建时间', auto_now=False, auto_now_add=True)),
                ('updated_at', fields.DatetimeField(description='更新时间', auto_now=True, auto_now_add=False)),
                ('conversation', fields.ForeignKeyField('models.Conversation', source_field='conversation_id', db_constraint=True, to_field='id', related_name='summaries', on_delete=OnDelete.CASCADE)),
                ('covers_until_message', fields.ForeignKeyField('models.Message', source_field='covers_until_message_id', description='封存游标:摘要覆盖到这条消息(含)为止', db_constraint=True, to_field='id', related_name='covering_summaries', on_delete=OnDelete.CASCADE)),
                ('summary_text', fields.TextField(description='中性摘要正文(成品,直接拼进上下文)', unique=False)),
                ('source_tokens', fields.IntField(default=0, description='压缩前上下文规模(API usage 上报)')),
                ('summary_tokens', fields.IntField(default=0, description='摘要正文的 token 数')),
                ('trigger', fields.CharField(default='threshold', description='触发原因:threshold(超线)/ manual(手动)/ overflow(超窗兜底)', max_length=32)),
                ('model_name', fields.CharField(default='', description='生成摘要用的模型', max_length=100)),
            ],
            options={'table': 'conversation_summaries', 'app': 'models', 'pk_attr': 'id', 'table_description': '一次封存事件的产物(append-only)。'},
            bases=['UUIDBaseModel', 'TimestampMixin'],
        ),
        ops.AddField(
            model_name='Conversation',
            name='context_tokens',
            field=fields.IntField(description='最近一轮上下文 token 数(API usage 上报,层 B 压缩触发判据)', db_default=0),
        ),
    ]
