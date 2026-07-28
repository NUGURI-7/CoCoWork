"""Provider / AIModel 的凭证列：裸 API Key → 凭证包 JSON。

改列语义是为了容下多凭证供应商（百度文档解析要 API Key + Secret Key）。
存量行原地重打包：解密 → 包成 {"api_key": ...} → 重新加密。

**自动生成的骨架不能直接用**：`makemigrations` 认不出「改名」，给的是
RemoveField + AddField，跑下去存量密钥全丢。已手工改成 RenameField。
"""

import json

from tortoise import connections, migrations
from tortoise.migrations import operations as ops

from app.core.encryption import decrypt, encrypt

_TABLES = ("providers", "ai_models")


async def _rewrite(transform) -> None:
    """逐行解密 → 变形 → 重新加密。正反两个方向共用。"""
    conn = connections.get("default")
    for table in _TABLES:
        rows = await conn.execute_query_dict(
            f"SELECT id, credentials_encrypted FROM {table}",
        )
        for row in rows:
            ciphertext = row["credentials_encrypted"]
            if not ciphertext:
                continue  # ai_models 留空 = 继承 Provider，没东西可转
            await conn.execute_query(
                f"UPDATE {table} SET credentials_encrypted = $1 WHERE id = $2",
                [encrypt(transform(decrypt(ciphertext))), row["id"]],
            )


async def repack(apps, schema_editor) -> None:
    """裸 key → {"api_key": 裸 key}。

    刻意不 import `services/model/credentials.py`——迁移是历史快照，凭证模型
    以后会长新字段、改校验规则，跟着它走的话今天能跑的迁移明天就跑不动了。
    这里只依赖「那一刻的形状是 {"api_key": ...}」这个死事实。
    """
    await _rewrite(lambda plain: json.dumps({"api_key": plain}))


async def unpack(apps, schema_editor) -> None:
    """凭证包 → 裸 key。回滚用——多出来的 secret_key 会丢，但回滚意味着代码
    也退回了旧版本，旧版本本来就不认识它。"""
    await _rewrite(lambda packed: json.loads(packed).get("api_key", ""))


class Migration(migrations.Migration):
    dependencies = [('models', '0020_add_paragraph_meta')]

    initial = False

    operations = [
        ops.RenameField(
            model_name='Provider',
            old_name='api_key_encrypted',
            new_name='credentials_encrypted',
        ),
        ops.RenameField(
            model_name='AIModel',
            old_name='api_key_encrypted',
            new_name='credentials_encrypted',
        ),
        # 排在两个改名之后：跑到这里时列已经是新名字了
        ops.RunPython(repack, unpack),
    ]
