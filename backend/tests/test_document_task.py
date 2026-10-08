"""文档任务失败处理单测 —— `_run_step` 的重试分流，零 DB 零 SAQ。

两个任务（解析 / 建索引）共用 `_run_step`：还有重试机会时 stage 退回 queued，
用尽时标 failed 并记错误信息、stage 不动（留给用户重试时分流）。两种情况都必须
重抛，否则 SAQ 会把 job 记成成功。写库那一下 monkeypatch 成记账的假模型。
"""

from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.models.knowledge import DocStage, DocStatus
from app.tasks import document_task


class _FakeDocumentModel:
    """记下每次 `filter(...).update(...)` 写入的字段。"""

    def __init__(self) -> None:
        self.updates: list[dict] = []

    def filter(self, *args, **kwargs):
        updates = self.updates

        class _QuerySet:
            async def update(self, **fields):
                updates.append(fields)
                return 1

        return _QuerySet()


@pytest.fixture
def fake_model(monkeypatch):
    model = _FakeDocumentModel()
    monkeypatch.setattr(document_task, "Document", model)
    return model


def _ctx(retryable: bool):
    return {"job": SimpleNamespace(retryable=retryable, attempts=1, retries=3)}


async def _failing_step(doc_id):
    raise RuntimeError("boom")


async def test_success_does_not_touch_status(fake_model):
    called = []

    async def step(doc_id):
        called.append(doc_id)

    doc_id = uuid4()
    await document_task._run_step(_ctx(retryable=True), step, doc_id)

    assert called == [doc_id]
    assert fake_model.updates == []


async def test_retryable_failure_requeues_and_reraises(fake_model):
    """还有重试机会：只把 stage 退回 queued，status 不动，异常照抛。"""
    with pytest.raises(RuntimeError, match="boom"):
        await document_task._run_step(_ctx(retryable=True), _failing_step, uuid4())

    assert fake_model.updates == [{"stage": DocStage.QUEUED}]


async def test_final_failure_marks_failed_keeps_stage_and_reraises(fake_model):
    """重试用尽：标 failed + 错误信息，不写 stage（停在出错那步），异常照抛。"""
    with pytest.raises(RuntimeError, match="boom"):
        await document_task._run_step(_ctx(retryable=False), _failing_step, uuid4())

    assert fake_model.updates == [{
        "status": DocStatus.FAILED,
        "error_message": "RuntimeError: boom",
    }]
