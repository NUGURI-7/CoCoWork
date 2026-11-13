"""删模型前的引用检查：提示文案与点名上限。查库那半在开发库上实测过，这里只测拼提示。"""

from uuid import uuid4

import pytest

from app.core.exceptions import Conflict409
from app.services.model import references


async def test_unused_models_pass(monkeypatch):
    async def none(_ids):
        return []
    monkeypatch.setattr(references, "find_model_references", none)
    await references.ensure_models_unused([uuid4()], target="这个模型")


async def test_names_users_in_message(monkeypatch):
    async def two(_ids):
        return ["Agent「资料员」", "工作空间「年报分析」的 Supervisor"]
    monkeypatch.setattr(references, "find_model_references", two)
    with pytest.raises(Conflict409) as exc:
        await references.ensure_models_unused([uuid4()], target="这个模型")
    assert exc.value.message == (
        "这个模型正被Agent「资料员」、工作空间「年报分析」的 Supervisor使用，"
        "请先给它们换一个模型再删除"
    )


async def test_caps_named_users(monkeypatch):
    async def many(_ids):
        return [f"Agent「A{i}」" for i in range(8)]
    monkeypatch.setattr(references, "find_model_references", many)
    with pytest.raises(Conflict409) as exc:
        await references.ensure_models_unused([uuid4()], target="这个模型")
    assert "A4" in exc.value.message and "A5" not in exc.value.message
    assert "等 8 处" in exc.value.message


async def test_no_ids_skips_query():
    assert await references.find_model_references([]) == []
