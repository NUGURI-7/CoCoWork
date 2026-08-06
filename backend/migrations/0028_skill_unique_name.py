from tortoise import migrations
from tortoise.migrations import operations as ops
from app.models.skill import SkillSource
from tortoise import fields
from tortoise.migrations.constraints import UniqueConstraint

class Migration(migrations.Migration):
    dependencies = [('models', '0027_add_interrupted_status')]

    initial = False

    operations = [
        ops.AlterField(
            model_name='Skill',
            name='source_type',
            field=fields.CharEnumField(default=SkillSource.USER, description='来源溯源。本表当前恒为 user；builtin 这个取值是留给列表接口出参复用的（内置那份从注册表构造），不落本表', enum_type=SkillSource, max_length=16),
        ),
        ops.AddConstraint(
            model_name='Skill',
            constraint=UniqueConstraint(fields=('created_by', 'name'), name=None),
        ),
    ]
