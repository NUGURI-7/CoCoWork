# 数据库迁移

CoCoWork 使用 **Tortoise ORM 1.x 内置迁移**（不引入 aerich）。
本目录由 `tortoise init` 自动初始化，存放各 app 的迁移历史。

## 配置位置

- Tortoise 配置字典：`app/db/postgresql.py` 里的 `TORTOISE_CONFIG`
- CLI 入口：`pyproject.toml` 的 `[tool.tortoise] tortoise_orm = "app.db.postgresql.TORTOISE_CONFIG"`
- CLI 调用时**无需** `-c` 参数，自动读取 `pyproject.toml`

## 首次初始化（仅一次，PG 上 `cocowork` 数据库已建好后执行）

```bash
cd backend
uv run tortoise init
```

会在 `backend/migrations/models/` 下生成 app 的迁移目录。

## 新增/修改模型后的标准流程

```bash
cd backend

# 1) 根据模型变更生成迁移文件
uv run tortoise makemigrations -n <change_description>

# 2) 把迁移应用到数据库
uv run tortoise migrate
```

> `-n` 指定的名字会出现在生成的迁移文件里，描述本次变更（如 `init_user`、`add_user_avatar`）。

## 其他常用命令

| 命令 | 作用 |
|---|---|
| `uv run tortoise history` | 列出数据库里已应用的迁移 |
| `uv run tortoise heads` | 列出磁盘上各 app 的当前 head 迁移 |
| `uv run tortoise sqlmigrate` | 打印某个迁移对应的 SQL，不执行 |
| `uv run tortoise downgrade` | 回滚迁移 |
| `uv run tortoise migrate --dry-run` | 预演应用，不真正执行 |
| `uv run tortoise migrate --fake` | 仅记录已执行，不跑 SQL（用于已手工同步的场景） |

## 注意

- 生成的迁移文件**必须入 git**，团队共享同一份迁移历史
- 不要手工编辑已应用过的迁移；如需调整，新建一个迁移文件来修正
- 切勿在生产环境跑 `downgrade` 除非有备份
