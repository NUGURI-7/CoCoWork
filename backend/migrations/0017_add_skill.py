from tortoise import migrations
from tortoise.migrations import operations as ops
from app.models.skill import SkillSource
from orjson import loads
from tortoise.fields.base import OnDelete
from tortoise.fields.data import JSON_DUMPS
from uuid_utils.compat import uuid7
from tortoise import fields

class Migration(migrations.Migration):
    dependencies = [('models', '0016_add_kb_retrieval_settings')]

    initial = False

    operations = [
        ops.CreateModel(
            name='Skill',
            fields=[
                ('id', fields.UUIDField(primary_key=True, default=uuid7, unique=True, db_index=True)),
                ('created_at', fields.DatetimeField(description='创建时间', auto_now=False, auto_now_add=True)),
                ('updated_at', fields.DatetimeField(description='更新时间', auto_now=True, auto_now_add=False)),
                ('created_by', fields.ForeignKeyField('models.User', source_field='created_by_id', db_constraint=True, to_field='id', related_name='skills', on_delete=OnDelete.CASCADE)),
                ('name', fields.CharField(description='SKILL.md 的 name，LLM 可见标识（agentskills 规范：小写字母/数字/连字符，≤64）', max_length=64)),
                ('description', fields.CharField(description='SKILL.md 的 description，进 system prompt 供 LLM 判断是否该用（规范上限 1024）', max_length=1024)),
                ('source_type', fields.CharEnumField(default=SkillSource.USER, description='来源溯源：builtin 为预置包（seed 入库）/ user 为上传。仅用于 UI 区分与 seed 幂等判断，不是权限位——两者都可删改', enum_type=SkillSource, max_length=16)),
                ('storage_key', fields.CharField(default='', description='zip 包在对象存储中的 key', max_length=512)),
                ('credentials_encrypted', fields.TextField(null=True, description='运行所需环境变量 dict（整体 JSON Fernet 加密，同 MCPServer.headers_encrypted）；运行时解密后经 docker run -e 注入；无则 NULL', unique=False)),
                ('skill_metadata', fields.JSONField(default=dict, description='原包文件清单等展示用信息（抄 Dify skill_metadata）；运行必需的字段一律提成列，不塞这里', encoder=JSON_DUMPS, decoder=loads)),
                ('enabled', fields.BooleanField(default=True, description='是否启用')),
            ],
            options={'table': 'skills', 'app': 'models', 'pk_attr': 'id', 'table_description': '一个可挂载到 agent 的 skill。'},
            bases=['UUIDBaseModel', 'TimestampMixin'],
        ),
    ]
