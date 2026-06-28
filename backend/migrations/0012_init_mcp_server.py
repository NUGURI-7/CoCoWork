from tortoise import migrations
from tortoise.migrations import operations as ops
from app.models.mcp import MCPTransport
from tortoise.fields.base import OnDelete
from uuid_utils.compat import uuid7
from tortoise import fields

class Migration(migrations.Migration):
    dependencies = [('models', '0011_init_workspace')]

    initial = False

    operations = [
        ops.CreateModel(
            name='MCPServer',
            fields=[
                ('id', fields.UUIDField(primary_key=True, default=uuid7, unique=True, db_index=True)),
                ('created_at', fields.DatetimeField(description='创建时间', auto_now=False, auto_now_add=True)),
                ('updated_at', fields.DatetimeField(description='更新时间', auto_now=True, auto_now_add=False)),
                ('created_by', fields.ForeignKeyField('models.User', source_field='created_by_id', db_constraint=True, to_field='id', related_name='mcp_servers', on_delete=OnDelete.CASCADE)),
                ('name', fields.CharField(description='显示名', max_length=100)),
                ('server_url', fields.CharField(description='MCP server 端点 URL', max_length=1024)),
                ('transport', fields.CharEnumField(default=MCPTransport.STREAMABLE_HTTP, description='传输协议：streamable_http（推荐）/ sse（降级）', enum_type=MCPTransport, max_length=32)),
                ('headers_encrypted', fields.TextField(null=True, description='自定义请求头 dict（含鉴权 token，Fernet 加密；无则 NULL）', unique=False)),
                ('description', fields.CharField(default='', description='备注', max_length=500)),
                ('enabled', fields.BooleanField(default=True, description='是否启用')),
            ],
            options={'table': 'mcp_servers', 'app': 'models', 'pk_attr': 'id', 'table_description': '用户配置的外部 MCP server（Client 侧）。'},
            bases=['UUIDBaseModel', 'TimestampMixin'],
        ),
    ]
