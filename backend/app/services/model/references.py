"""模型被谁用着 —— 删模型、删供应商之前的引用检查。

模型 ID 散在三处：
- agents.config 的模型槽位（jsonb）
- workspaces.supervisor 的模型槽位（jsonb，结构同 AgentConfig）
- knowledge_bases.embedding_model（外键，RESTRICT）

前两处是 jsonb，数据库管不到 —— 不在删除前查，模型删了 Agent 还指着它，
等到聊天时才炸。外键那处数据库会拦，但拦下来是一个看不懂的完整性错误，
一并在这里查，给出能看懂的提示。

槽位用 jsonb_each 遍历而不是逐个列出 chat / tts / vision……：以后加槽位，
这里不用跟着改。
"""

from uuid import UUID

from tortoise import connections

from app.core.exceptions import Conflict409

# 提示里最多点名几处，其余合成「等 N 处」
_MAX_NAMED = 5

_SQL = """
SELECT 'Agent「' || name || '」' AS label, created_at FROM agents
WHERE EXISTS (
    SELECT 1 FROM jsonb_each(COALESCE(config->'models', '{}'::jsonb)) AS slot
    WHERE jsonb_typeof(slot.value) = 'object' AND slot.value->>'id' = ANY($1::text[])
)
UNION ALL
SELECT '工作空间「' || name || '」的 Supervisor', created_at FROM workspaces
WHERE EXISTS (
    SELECT 1 FROM jsonb_each(COALESCE(supervisor->'models', '{}'::jsonb)) AS slot
    WHERE jsonb_typeof(slot.value) = 'object' AND slot.value->>'id' = ANY($1::text[])
)
UNION ALL
SELECT '知识库「' || name || '」', created_at FROM knowledge_bases
WHERE embedding_model_id::text = ANY($1::text[])
ORDER BY created_at
"""


async def find_model_references(model_ids: list[UUID]) -> list[str]:
    """返回正在使用这些模型的地方，如「Agent『资料员』」，按创建时间排序。"""
    if not model_ids:
        return []
    rows = await connections.get("default").execute_query_dict(
        _SQL, [[str(i) for i in model_ids]],
    )
    return [r["label"] for r in rows]


async def ensure_models_unused(model_ids: list[UUID], *, target: str) -> None:
    """有人在用就拒绝删除，说清是谁在用、该怎么办。

    target：提示里怎么称呼要删的东西，如「这个模型」「这个供应商下的模型」。
    """
    labels = await find_model_references(model_ids)
    if not labels:
        return
    named = "、".join(labels[:_MAX_NAMED])
    if len(labels) > _MAX_NAMED:
        named += f"等 {len(labels)} 处"
    raise Conflict409(f"{target}正被{named}使用，请先给它们换一个模型再删除")
