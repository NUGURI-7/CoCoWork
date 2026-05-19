# Tortoise ORM 迁移指南

> tortoise-orm >= 1.1.7，aerich 已废弃。

## 日常工作流

```bash
# 修改 model 后生成迁移
uv run tortoise makemigrations --name describe_change

# 应用迁移
uv run tortoise migrate

# 查看已应用记录
uv run tortoise history
```

## 数据迁移（RunSQL）

```bash
uv run tortoise makemigrations --empty models --name seed_something
```

然后编辑生成的文件：

```python
from tortoise.migrations import operations as ops

class Migration(migrations.Migration):
    dependencies = [("models", "0002_prev")]
    operations = [
        ops.RunSQL(
            sql="INSERT INTO ...",
            reverse_sql="DELETE FROM ...",
        ),
    ]
```

## 迁移文件位置

`backend/migrations/` — Python 包，已纳入 git 管理。

## pyproject.toml 配置

```toml
[tool.tortoise]
tortoise_orm = "app.core.config.TORTOISE_CONFIG"
```

migrations 路径在 `TORTOISE_CONFIG` 的 app 配置里：

```python
"apps": {
    "models": {
        "models": [...],
        "default_connection": "default",
        "migrations": "migrations",
    }
}
```

## 回滚

```bash
uv run tortoise downgrade models 0002_seed_admin
```
