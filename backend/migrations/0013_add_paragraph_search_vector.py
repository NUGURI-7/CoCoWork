from tortoise import migrations
from tortoise.migrations import operations as ops
from app.db.fields import TSVectorField

class Migration(migrations.Migration):
    dependencies = [('models', '0012_init_mcp_server')]

    initial = False

    operations = [
        ops.AddField(
            model_name='Paragraph',
            name='search_vector',
            field=TSVectorField(null=True, description='全文检索词料（jieba 分词 → tsvector，建 GIN 索引）', generated=False, unique=False),
        ),
    ]
