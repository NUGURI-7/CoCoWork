from tortoise import migrations
from tortoise.migrations import operations as ops
from tortoise.fields.base import OnDelete
from uuid_utils.compat import uuid7
from tortoise import fields

class Migration(migrations.Migration):
    dependencies = [('models', '0018_index_foreign_keys')]

    initial = False

    operations = [
        ops.CreateModel(
            name='SandboxArtifact',
            fields=[
                ('id', fields.UUIDField(primary_key=True, default=uuid7, unique=True, db_index=True)),
                ('created_at', fields.DatetimeField(description='创建时间', auto_now=False, auto_now_add=True)),
                ('updated_at', fields.DatetimeField(description='更新时间', auto_now=True, auto_now_add=False)),
                ('created_by', fields.ForeignKeyField('models.User', source_field='created_by_id', db_index=True, description='产物归属人。下载鉴权走它——Playground 与 workspace 两条路都有值', db_constraint=True, to_field='id', related_name='sandbox_artifacts', on_delete=OnDelete.CASCADE)),
                ('conversation', fields.ForeignKeyField('models.Conversation', source_field='conversation_id', null=True, db_index=True, description='workspace 对话产出的填此项；Playground 无对话，为 NULL', db_constraint=True, to_field='id', related_name='sandbox_artifacts', on_delete=OnDelete.CASCADE)),
                ('message_id', fields.UUIDField(db_index=True, description='产出它的那条 assistant 消息 ID。刻意不做外键——Playground 的消息不入库，做了 FK 就插不进来')),
                ('filename', fields.CharField(description='交付区里的文件名，也是下载时给浏览器的名字', max_length=255)),
                ('size', fields.IntField(description='字节数')),
                ('content_type', fields.CharField(description='由扩展名推出的 MIME 类型；下载接口据此决定浏览器内联渲染还是另存', max_length=128)),
                ('storage_key', fields.CharField(description='对象存储的键：sandbox/{scope_id}/{message_id}/{filename}', max_length=512)),
            ],
            options={'table': 'sandbox_artifacts', 'app': 'models', 'unique_together': (('message_id', 'filename'),), 'pk_attr': 'id', 'table_description': '一轮回复交付出来的一个文件。'},
            bases=['UUIDBaseModel', 'TimestampMixin'],
        ),
    ]
