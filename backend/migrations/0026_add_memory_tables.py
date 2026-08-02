from tortoise import migrations
from tortoise.migrations import operations as ops
from tortoise.fields.base import OnDelete
from uuid_utils.compat import uuid7
from tortoise import fields

class Migration(migrations.Migration):
    dependencies = [('models', '0025_clarify_source_tokens')]

    initial = False

    operations = [
        ops.CreateModel(
            name='UserMemory',
            fields=[
                ('id', fields.UUIDField(primary_key=True, default=uuid7, unique=True, db_index=True)),
                ('created_at', fields.DatetimeField(description='创建时间', auto_now=False, auto_now_add=True)),
                ('updated_at', fields.DatetimeField(description='更新时间', auto_now=True, auto_now_add=False)),
                ('user', fields.OneToOneField('models.User', source_field='user_id', description='归属用户 —— OneToOne 保证一人一份', db_constraint=True, to_field='id', related_name='memory', on_delete=OnDelete.CASCADE)),
                ('content', fields.TextField(default='', description='记忆正文(成品,直接拼进 system prompt)', unique=False)),
            ],
            options={'table': 'user_memories', 'app': 'models', 'pk_attr': 'id', 'table_description': '一个用户一份的全局常驻记忆。'},
            bases=['UUIDBaseModel', 'TimestampMixin'],
        ),
        ops.CreateModel(
            name='WorkspaceMemory',
            fields=[
                ('id', fields.UUIDField(primary_key=True, default=uuid7, unique=True, db_index=True)),
                ('created_at', fields.DatetimeField(description='创建时间', auto_now=False, auto_now_add=True)),
                ('updated_at', fields.DatetimeField(description='更新时间', auto_now=True, auto_now_add=False)),
                ('workspace', fields.ForeignKeyField('models.Workspace', source_field='workspace_id', description='所属工作区', db_constraint=True, to_field='id', related_name='memories', on_delete=OnDelete.CASCADE)),
                ('user', fields.ForeignKeyField('models.User', source_field='user_id', db_index=True, description='记忆属于谁', db_constraint=True, to_field='id', related_name='workspace_memories', on_delete=OnDelete.CASCADE)),
                ('content', fields.TextField(default='', description='记忆正文(成品,直接拼进 system prompt)', unique=False)),
            ],
            options={'table': 'workspace_memories', 'app': 'models', 'unique_together': (('workspace', 'user'),), 'pk_attr': 'id', 'table_description': '一个人在一个工作区里的局部常驻记忆。'},
            bases=['UUIDBaseModel', 'TimestampMixin'],
        ),
    ]
