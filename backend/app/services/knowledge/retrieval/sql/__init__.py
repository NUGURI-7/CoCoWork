"""检索 SQL 加载器：按名取文件，进程内缓存，一处收口。

约定：本目录下一个 ``.sql`` 文件 = 一条检索查询，文件头注释写清占位符含义。
新增检索模式（hybrid / keyword）= 扔新文件进来 + ``load_sql("<名字>")``。
"""
from functools import cache
from pathlib import Path

_SQL_DIR = Path(__file__).parent


@cache
def load_sql(name: str) -> str:
    """读 ``sql/<name>.sql`` 全文。@cache：每个名字只读一次磁盘，之后走内存。"""
    return (_SQL_DIR / f"{name}.sql").read_text(encoding="utf-8")
