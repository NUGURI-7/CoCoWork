from tortoise import migrations
from tortoise.migrations import operations as ops
from orjson import loads
from tortoise.fields.base import OnDelete
from tortoise.fields.data import JSON_DUMPS
from uuid_utils.compat import uuid7
from tortoise import fields

class Migration(migrations.Migration):
    dependencies = [('models', '0008_embedding_enum_source_type')]

    initial = False

    operations = [
        ops.CreateModel(
            name='Agent',
            fields=[
                ('id', fields.UUIDField(primary_key=True, default=uuid7, unique=True, db_index=True)),
                ('created_at', fields.DatetimeField(description='创建时间', auto_now=False, auto_now_add=True)),
                ('updated_at', fields.DatetimeField(description='更新时间', auto_now=True, auto_now_add=False)),
                ('created_by', fields.ForeignKeyField('models.User', source_field='created_by_id', db_constraint=True, to_field='id', related_name='agents', on_delete=OnDelete.CASCADE)),
                ('name', fields.CharField(description='Agent 名字', max_length=150)),
                ('description', fields.CharField(default='', description='描述', max_length=500)),
                ('template', fields.CharField(description='引用的内置模板 key（如 researcher / ppt），指向代码里的模板注册表', max_length=64)),
                ('config', fields.JSONField(default=dict, description='填料：行为（prompt/model）+ 挂载资源（knowledge/tools/skills 的 id 列表）', encoder=JSON_DUMPS, decoder=loads)),
            ],
            options={'table': 'agents', 'app': 'models', 'pk_attr': 'id', 'table_description': '用户创建的 Agent（NPC）：模板引用 + config 填料。'},
            bases=['UUIDBaseModel', 'TimestampMixin'],
        ),
    ]
