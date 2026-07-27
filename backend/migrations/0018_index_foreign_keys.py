from tortoise import migrations
from tortoise.migrations import operations as ops
from tortoise.fields.base import OnDelete
from tortoise import fields

class Migration(migrations.Migration):
    dependencies = [('models', '0017_add_skill')]

    initial = False

    operations = [
        ops.AlterField(
            model_name='Document',
            name='knowledge_base',
            field=fields.ForeignKeyField('models.KnowledgeBase', source_field='knowledge_base_id', db_index=True, db_constraint=True, to_field='id', related_name='documents', on_delete=OnDelete.CASCADE),
        ),
        ops.AlterField(
            model_name='Embedding',
            name='document',
            field=fields.ForeignKeyField('models.Document', source_field='document_id', db_index=True, db_constraint=True, to_field='id', related_name='embeddings', on_delete=OnDelete.CASCADE),
        ),
        ops.AlterField(
            model_name='Embedding',
            name='knowledge_base',
            field=fields.ForeignKeyField('models.KnowledgeBase', source_field='knowledge_base_id', db_index=True, db_constraint=True, to_field='id', related_name='embeddings', on_delete=OnDelete.CASCADE),
        ),
        ops.AlterField(
            model_name='Embedding',
            name='paragraph',
            field=fields.ForeignKeyField('models.Paragraph', source_field='paragraph_id', db_index=True, description='始终有——命中后据此返回整段', db_constraint=True, to_field='id', related_name='embeddings', on_delete=OnDelete.CASCADE),
        ),
        ops.AlterField(
            model_name='Message',
            name='conversation',
            field=fields.ForeignKeyField('models.Conversation', source_field='conversation_id', db_index=True, db_constraint=True, to_field='id', related_name='messages', on_delete=OnDelete.CASCADE),
        ),
        ops.AlterField(
            model_name='Paragraph',
            name='document',
            field=fields.ForeignKeyField('models.Document', source_field='document_id', db_index=True, db_constraint=True, to_field='id', related_name='paragraphs', on_delete=OnDelete.CASCADE),
        ),
        ops.AlterField(
            model_name='Paragraph',
            name='knowledge_base',
            field=fields.ForeignKeyField('models.KnowledgeBase', source_field='knowledge_base_id', db_index=True, db_constraint=True, to_field='id', related_name='paragraphs', on_delete=OnDelete.CASCADE),
        ),
        ops.AlterField(
            model_name='Skill',
            name='created_by',
            field=fields.ForeignKeyField('models.User', source_field='created_by_id', db_index=True, db_constraint=True, to_field='id', related_name='skills', on_delete=OnDelete.CASCADE),
        ),
    ]
