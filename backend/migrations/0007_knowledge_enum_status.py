from tortoise import migrations
from tortoise.migrations import operations as ops
from app.models.knowledge import DocStage, DocStatus, KBStatus
from tortoise import fields

class Migration(migrations.Migration):
    dependencies = [('models', '0006_add_aimodel_meta')]

    initial = False

    operations = [
        ops.AlterField(
            model_name='Document',
            name='stage',
            field=fields.CharEnumField(default=DocStage.NONE, description='处理阶段（pending / completed 时为空）', enum_type=DocStage, max_length=20),
        ),
        ops.AlterField(
            model_name='Document',
            name='status',
            field=fields.CharEnumField(default=DocStatus.PENDING, description='处理状态', enum_type=DocStatus, max_length=20),
        ),
        ops.AlterField(
            model_name='KnowledgeBase',
            name='status',
            field=fields.CharEnumField(default=KBStatus.READY, description='库级状态（换模型重建时切 reindexing）', enum_type=KBStatus, max_length=20),
        ),
    ]
