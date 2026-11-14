from tortoise import migrations
from tortoise.migrations import operations as ops
from tortoise.fields.base import OnDelete
from tortoise import fields

class Migration(migrations.Migration):
    dependencies = [('models', '0036_agent_is_enabled')]

    initial = False

    operations = [
        ops.AddField(
            model_name='User',
            name='is_guest',
            field=fields.BooleanField(default=False, description='官网体验的临时账号', db_default=False),
        ),
        ops.AddField(
            model_name='Workspace',
            name='cloned_from',
            field=fields.ForeignKeyField('models.Workspace', source_field='cloned_from_id', null=True, description='复制来源的模板工作空间；自己新建的为空', db_constraint=True, to_field='id', related_name='clones', on_delete=OnDelete.SET_NULL),
        ),
    ]
