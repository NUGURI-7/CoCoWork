from tortoise import migrations
from tortoise.migrations import operations as ops

class Migration(migrations.Migration):
    dependencies = [('models', '0013_add_paragraph_search_vector')]

    initial = False

    operations = [
        ops.RunSQL(
            'CREATE INDEX idx_paragraphs_search_vector '
            'ON paragraphs USING GIN (search_vector);',
        ),
    ]