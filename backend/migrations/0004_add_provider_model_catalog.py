from tortoise import migrations
from tortoise.migrations import operations as ops
from uuid_utils.compat import uuid7
from tortoise import fields

class Migration(migrations.Migration):
    dependencies = [('models', '0003_drop_sort_order_and_unique')]

    initial = False

    operations = [
        ops.CreateModel(
            name='ProviderModelCatalog',
            fields=[
                ('id', fields.UUIDField(primary_key=True, default=uuid7, unique=True, db_index=True)),
                ('provider_type', fields.CharField(description='供应商类型', max_length=50)),
                ('model_id', fields.CharField(description='上游模型标识', max_length=100)),
                ('model_type', fields.CharField(description='chat / embedding / rerank', max_length=20)),
            ],
            options={'table': 'provider_model_catalog', 'app': 'models', 'unique_together': (('provider_type', 'model_id'),), 'pk_attr': 'id', 'table_description': '供应商可用模型目录。'},
            bases=['UUIDBaseModel'],
        ),
        ops.AlterModelOptions(
            name='AIModel',
            options={'table': 'ai_models', 'app': 'models', 'pk_attr': 'id', 'table_description': '具体模型实例，挂在 Provider 下。'},
        ),
        ops.AddField(
            model_name='AIModel',
            name='api_key_encrypted',
            field=fields.TextField(default='', description='覆盖 Provider 的 API Key（留空继承）', unique=False),
        ),
        ops.AddField(
            model_name='AIModel',
            name='base_url',
            field=fields.CharField(default='', description='覆盖 Provider 的 base URL（留空继承）', max_length=512),
        ),
        ops.AlterModelOptions(
            name='Provider',
            options={'table': 'providers', 'app': 'models', 'unique_together': (('created_by', 'name'),), 'pk_attr': 'id', 'table_description': '上游模型服务供应商。'},
        ),
        ops.AlterField(
            model_name='Provider',
            name='api_key_encrypted',
            field=fields.TextField(description='默认 API Key（加密）', unique=False),
        ),
        ops.AlterField(
            model_name='Provider',
            name='base_url',
            field=fields.CharField(description='默认 API base URL', max_length=512),
        ),
        ops.RemoveField(model_name='Provider', name='is_enabled'),
        ops.RemoveField(model_name='Provider', name='is_global'),
    ]
