from tortoise import migrations
from tortoise.migrations import operations as ops
from app.models.knowledge import ParseBackend
from tortoise import fields

class Migration(migrations.Migration):
    dependencies = [('models', '0022_add_kb_parse_backend')]

    initial = False

    operations = [
        ops.AddField(
            model_name='Document',
            name='parse_backend',
            field=fields.CharEnumField(default=ParseBackend.LOCAL, description='实际用的解析后端 —— 库上那个是期望，这里是事实（降级时两者不一致）', db_default='local', enum_type=ParseBackend, max_length=20),
        ),
    ]
