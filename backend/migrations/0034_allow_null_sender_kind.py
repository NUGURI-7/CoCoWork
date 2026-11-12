from tortoise import migrations
from tortoise.migrations import operations as ops
from app.models.workspace.message_model import SenderKind
from tortoise import fields

class Migration(migrations.Migration):
    dependencies = [('models', '0033_require_conversation_owner')]

    initial = False

    operations = [
        ops.AlterField(
            model_name='Message',
            name='sender_kind',
            field=fields.CharEnumField(null=True, description='业务层发送方:user/supervisor/member。只在工作空间会话中填,独立 Agent 会话为空', enum_type=SenderKind, max_length=16),
        ),
    ]
