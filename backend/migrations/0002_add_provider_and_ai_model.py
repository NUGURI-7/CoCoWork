from tortoise import migrations
from tortoise.migrations import operations as ops
import functools
from json import dumps, loads
from tortoise.fields.base import OnDelete
from uuid_utils.compat import uuid7
from tortoise import fields

class Migration(migrations.Migration):
    dependencies = [('models', '0001_init_user')]

    initial = False

    operations = [
        ops.CreateModel(
            name='Provider',
            fields=[
                ('id', fields.UUIDField(primary_key=True, default=uuid7, unique=True, db_index=True)),
                ('created_at', fields.DatetimeField(description='创建时间', auto_now=False, auto_now_add=True)),
                ('updated_at', fields.DatetimeField(description='更新时间', auto_now=True, auto_now_add=False)),
                ('created_by', fields.ForeignKeyField('models.User', source_field='created_by_id', db_constraint=True, to_field='id', related_name='providers', on_delete=OnDelete.CASCADE)),
                ('name', fields.CharField(description='显示名', max_length=100)),
                ('provider_type', fields.CharField(description='服务商类型', max_length=50)),
                ('base_url', fields.CharField(description='API base URL', max_length=512)),
                ('api_key_encrypted', fields.TextField(description='加密后的 API Key', unique=False)),
                ('description', fields.CharField(default='', description='备注', max_length=500)),
                ('is_global', fields.BooleanField(default=False, description='全局可见（仅 admin 可创建）')),
                ('is_enabled', fields.BooleanField(default=True, description='是否启用')),
                ('sort_order', fields.IntField(default=0, description='排序权重')),
            ],
            options={'table': 'providers', 'app': 'models', 'unique_together': (('created_by', 'name'),), 'pk_attr': 'id', 'table_description': '上游模型服务凭证（全局 or 个人）。'},
            bases=['UUIDBaseModel', 'TimestampMixin'],
        ),
        ops.CreateModel(
            name='AIModel',
            fields=[
                ('id', fields.UUIDField(primary_key=True, default=uuid7, unique=True, db_index=True)),
                ('created_at', fields.DatetimeField(description='创建时间', auto_now=False, auto_now_add=True)),
                ('updated_at', fields.DatetimeField(description='更新时间', auto_now=True, auto_now_add=False)),
                ('provider', fields.ForeignKeyField('models.Provider', source_field='provider_id', db_constraint=True, to_field='id', related_name='models', on_delete=OnDelete.CASCADE)),
                ('model_name', fields.CharField(description='上游模型 ID', max_length=100)),
                ('display_name', fields.CharField(description='前端展示名', max_length=100)),
                ('model_type', fields.CharField(description='chat / embedding / rerank', max_length=20)),
                ('config', fields.JSONField(default=dict, description='模型能力元数据', encoder=functools.partial(dumps, separators=(',', ':')), decoder=loads)),
                ('is_enabled', fields.BooleanField(default=True, description='是否启用')),
                ('sort_order', fields.IntField(default=0, description='排序权重')),
            ],
            options={'table': 'ai_models', 'app': 'models', 'unique_together': (('provider', 'model_name'),), 'pk_attr': 'id', 'table_description': '具体模型，挂在 Provider 下。'},
            bases=['UUIDBaseModel', 'TimestampMixin'],
        ),
    ]
