from tortoise import migrations
from tortoise.migrations import operations as ops
from app.models.workspace.message_model import MessageRole, MessageStatus, SenderKind
from orjson import loads
from tortoise.fields.base import OnDelete
from tortoise.fields.data import JSON_DUMPS
from uuid_utils.compat import uuid7
from tortoise import fields

class Migration(migrations.Migration):
    dependencies = [('models', '0010_drop_kb_provider_name_unique')]

    initial = False

    operations = [
        ops.CreateModel(
            name='Workspace',
            fields=[
                ('id', fields.UUIDField(primary_key=True, default=uuid7, unique=True, db_index=True)),
                ('created_at', fields.DatetimeField(description='创建时间', auto_now=False, auto_now_add=True)),
                ('updated_at', fields.DatetimeField(description='更新时间', auto_now=True, auto_now_add=False)),
                ('created_by', fields.ForeignKeyField('models.User', source_field='created_by_id', db_constraint=True, to_field='id', related_name='workspaces', on_delete=OnDelete.CASCADE)),
                ('name', fields.CharField(description='工作空间名字', max_length=150)),
                ('description', fields.CharField(default='', description='简介', max_length=500)),
                ('avatar_url', fields.CharField(default='', description='头像 URL', max_length=500)),
                ('supervisor', fields.JSONField(default=dict, description='内置管家配置（复用 AgentConfig schema：model / prompt / knowledge / tools）', encoder=JSON_DUMPS, decoder=loads)),
                ('config', fields.JSONField(default=dict, description='工作空间自身配置：路由策略 / 开场白 / 共享资源 id / 招募白名单 / UI 偏好', encoder=JSON_DUMPS, decoder=loads)),
            ],
            options={'table': 'workspaces', 'app': 'models', 'pk_attr': 'id', 'table_description': '工作空间本体。'},
            bases=['UUIDBaseModel', 'TimestampMixin'],
        ),
        ops.CreateModel(
            name='Conversation',
            fields=[
                ('id', fields.UUIDField(primary_key=True, default=uuid7, unique=True, db_index=True)),
                ('created_at', fields.DatetimeField(description='创建时间', auto_now=False, auto_now_add=True)),
                ('updated_at', fields.DatetimeField(description='更新时间', auto_now=True, auto_now_add=False)),
                ('workspace', fields.ForeignKeyField('models.Workspace', source_field='workspace_id', db_constraint=True, to_field='id', related_name='conversations', on_delete=OnDelete.CASCADE)),
                ('title', fields.CharField(default='', description='对话标题', max_length=150)),
                ('config', fields.JSONField(default=dict, description='对话级临时覆盖（换模型 / 开 thinking / 临时挂 KB 等扩展口子）', encoder=JSON_DUMPS, decoder=loads)),
            ],
            options={'table': 'conversations', 'app': 'models', 'pk_attr': 'id', 'table_description': 'workspace 里的一条对话流。'},
            bases=['UUIDBaseModel', 'TimestampMixin'],
        ),
        ops.CreateModel(
            name='WorkspaceMember',
            fields=[
                ('id', fields.UUIDField(primary_key=True, default=uuid7, unique=True, db_index=True)),
                ('created_at', fields.DatetimeField(description='创建时间', auto_now=False, auto_now_add=True)),
                ('updated_at', fields.DatetimeField(description='更新时间', auto_now=True, auto_now_add=False)),
                ('workspace', fields.ForeignKeyField('models.Workspace', source_field='workspace_id', db_constraint=True, to_field='id', related_name='members', on_delete=OnDelete.CASCADE)),
                ('agent', fields.ForeignKeyField('models.Agent', source_field='agent_id', db_constraint=True, to_field='id', related_name='member_of', on_delete=OnDelete.CASCADE)),
                ('config', fields.JSONField(default=dict, description='成员在此 workspace 的覆盖配置（nickname / avatar / 特化 prompt 等）', encoder=JSON_DUMPS, decoder=loads)),
            ],
            options={'table': 'workspace_members', 'app': 'models', 'unique_together': (('workspace', 'agent'),), 'pk_attr': 'id', 'table_description': 'workspace 招进来的普通成员（agent 引用）。'},
            bases=['UUIDBaseModel', 'TimestampMixin'],
        ),
        ops.CreateModel(
            name='Message',
            fields=[
                ('id', fields.UUIDField(primary_key=True, default=uuid7, unique=True, db_index=True)),
                ('created_at', fields.DatetimeField(description='创建时间', auto_now=False, auto_now_add=True)),
                ('updated_at', fields.DatetimeField(description='更新时间', auto_now=True, auto_now_add=False)),
                ('conversation', fields.ForeignKeyField('models.Conversation', source_field='conversation_id', db_constraint=True, to_field='id', related_name='messages', on_delete=OnDelete.CASCADE)),
                ('role', fields.CharEnumField(description='协议层角色:user/assistant', enum_type=MessageRole, max_length=16)),
                ('sender_kind', fields.CharEnumField(description='业务层发送方:user/supervisor/member', enum_type=SenderKind, max_length=16)),
                ('sender_member', fields.ForeignKeyField('models.WorkspaceMember', source_field='sender_member_id', null=True, description='sender_kind=member 时填;member 被踢出后保留消息、字段置 NULL', db_constraint=True, to_field='id', related_name='messages', on_delete=OnDelete.SET_NULL)),
                ('content', fields.JSONField(default=list, description='消息内容:blocks 数组,对齐前端 chat.ts ContentBlock', encoder=JSON_DUMPS, decoder=loads)),
                ('mentioned_member_ids', fields.JSONField(default=list, description='被 @ 的 member id 数组(冗余字段,给路由/反查用)', encoder=JSON_DUMPS, decoder=loads)),
                ('status', fields.CharEnumField(default=MessageStatus.DONE, description='终态:done/error/stopped(流式中不入库)', enum_type=MessageStatus, max_length=16)),
                ('error_message', fields.CharField(default='', description='错误友好文案(给用户看,技术细节走 log)', max_length=500)),
            ],
            options={'table': 'messages', 'app': 'models', 'pk_attr': 'id', 'table_description': 'conversation 里的一条消息。'},
            bases=['UUIDBaseModel', 'TimestampMixin'],
        ),
    ]
