from tortoise import migrations
from tortoise.migrations import operations as ops
from app.models.knowledge import ParseBackend
from tortoise import fields

class Migration(migrations.Migration):
    dependencies = [('models', '0021_provider_credentials_bundle')]

    initial = False

    operations = [
        ops.AlterField(
            model_name='AIModel',
            name='credentials_encrypted',
            field=fields.TextField(default='', description='整包覆盖 Provider 的凭证（留空继承）', unique=False),
        ),
        ops.AddField(
            model_name='KnowledgeBase',
            name='parse_backend',
            field=fields.CharEnumField(default=ParseBackend.LOCAL, description='PDF 解析后端；local 零配置可用，baidu 结构更准但需部署侧配 Key', db_default='local', enum_type=ParseBackend, max_length=20),
        ),
        ops.AlterField(
            model_name='Provider',
            name='credentials_encrypted',
            field=fields.TextField(description='凭证包：Fernet 加密的 JSON，形状见 services/model/credentials.py', unique=False),
        ),
    ]
