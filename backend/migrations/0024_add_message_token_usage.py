from tortoise import migrations
from tortoise.migrations import operations as ops
from orjson import loads
from tortoise.fields.data import JSON_DUMPS
from tortoise import fields

class Migration(migrations.Migration):
    dependencies = [('models', '0023_add_document_parse_backend')]

    initial = False

    operations = [
        ops.AddField(
            model_name='Message',
            name='completion_tokens',
            field=fields.IntField(description='本轮全部模型调用的输出合计(含子 agent)', db_default=0),
        ),
        ops.AddField(
            model_name='Message',
            name='prompt_tokens',
            field=fields.IntField(description='本轮全部模型调用的输入合计(含子 agent)', db_default=0),
        ),
        ops.AddField(
            model_name='Message',
            name='token_usage',
            field=fields.JSONField(description='消耗明细:一行一个计费单元(supervisor 或一次派活),形如 [{delegate_id, prompt_tokens, completion_tokens}]', db_default=[], encoder=JSON_DUMPS, decoder=loads),
        ),
    ]
