from tortoise import migrations
from tortoise.migrations import operations as ops

class Migration(migrations.Migration):
    dependencies = [('models', '0009_init_agent')]

    initial = False

    operations = [
        ops.RemoveConstraint(
            model_name='KnowledgeBase',
            name=None,
            fields=['created_by', 'name'],
        ),
        ops.RemoveConstraint(
            model_name='Provider',
            name=None,
            fields=['created_by', 'name'],
        ),
    ]
