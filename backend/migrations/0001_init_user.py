from tortoise import migrations
from tortoise.migrations import operations as ops
from uuid_utils.compat import uuid7
from tortoise import fields

class Migration(migrations.Migration):
    initial = True

    operations = [
        ops.CreateModel(
            name='User',
            fields=[
                ('id', fields.UUIDField(primary_key=True, default=uuid7, unique=True, db_index=True)),
                ('created_at', fields.DatetimeField(description='创建时间', auto_now=False, auto_now_add=True)),
                ('updated_at', fields.DatetimeField(description='更新时间', auto_now=True, auto_now_add=False)),
                ('username', fields.CharField(unique=True, description='用户名（登录凭证）', max_length=20)),
                ('email', fields.CharField(unique=True, description='邮箱（注册必填）', max_length=255)),
                ('password_hash', fields.CharField(description='密码哈希', max_length=255)),
                ('nick_name', fields.CharField(default='', description='昵称（显示用）', max_length=50)),
                ('avatar_url', fields.CharField(default='', description='头像 URL', max_length=512)),
                ('is_active', fields.BooleanField(default=True, description='账户是否启用')),
                ('is_admin', fields.BooleanField(default=False, description='管理员标记')),
            ],
            options={'table': 'users', 'app': 'models', 'pk_attr': 'id', 'table_description': '用户实体。'},
            bases=['UUIDBaseModel', 'TimestampMixin'],
        ),
    ]
