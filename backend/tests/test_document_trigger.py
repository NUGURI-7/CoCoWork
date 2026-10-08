"""文档触发（解析 / 建索引）单测 —— 拒绝原因与入队失败回滚，零 DB 零 Redis。

`_reject_reason` 是纯函数，doc 用轻量假对象顶替；`_enqueue` 里写库的那一下
（`Document.filter(...).update(...)`）monkeypatch 成记账的假模型，只断言「回滚时
写回的是触发前的值」。条件更新本身（`_PARSABLE` / `_INDEXABLE` 进 WHERE）要真库
才有意义，不在这里测。
"""

from types import SimpleNamespace

import pytest

from app.models.knowledge import DocStage, DocStatus
from app.services.knowledge import document_service
from app.services.knowledge.document_service import DocumentService, _reject_reason


def _doc(status: DocStatus, stage: DocStage, error_message: str = ""):
    return SimpleNamespace(id="docid", status=status, stage=stage, error_message=error_message)


class _FakeDocumentModel:
    """记下每次 `filter(...).update(...)` 的 (过滤条件, 写入字段)。"""

    def __init__(self) -> None:
        self.updates: list[tuple[dict, dict]] = []

    def filter(self, *args, **kwargs):
        updates = self.updates

        class _QuerySet:
            async def update(self, **fields):
                updates.append((kwargs, fields))
                return 1

        return _QuerySet()


class _FakeTask:
    def __init__(self, fail: bool) -> None:
        self.name = "knowledge.fake"
        self.fail = fail
        self.enqueued: list[dict] = []

    async def enqueue(self, **kwargs):
        if self.fail:
            raise ConnectionError("redis down")
        self.enqueued.append(kwargs)


@pytest.fixture
def fake_model(monkeypatch):
    model = _FakeDocumentModel()
    monkeypatch.setattr(document_service, "Document", model)
    return model


# === _reject_reason ===

@pytest.mark.parametrize(
    ("status", "stage", "expected"),
    [
        (DocStatus.PROCESSING, DocStage.PARSING, "文档处理中，请稍候"),
        (DocStatus.PROCESSING, DocStage.QUEUED, "文档处理中，请稍候"),
        (DocStatus.PENDING, DocStage.NONE, "文档尚未上传完成"),
        (DocStatus.PENDING, DocStage.UPLOADED, "文档尚未解析"),
        (DocStatus.FAILED, DocStage.PARSING, "解析失败，请先重新解析"),
        (DocStatus.FAILED, DocStage.SPLITTING, "解析失败，请先重新解析"),
    ],
)
def test_reject_reason(status, stage, expected):
    assert _reject_reason(_doc(status, stage)) == expected


# === _enqueue ===

async def test_enqueue_success_does_not_touch_status(fake_model):
    """入队成功：任务带上 doc_id，不写库。"""
    task = _FakeTask(fail=False)
    ok = await DocumentService._enqueue(_doc(DocStatus.PARSED, DocStage.NONE), task)

    assert ok is True
    assert task.enqueued == [{"doc_id": "docid"}]
    assert fake_model.updates == []


async def test_enqueue_failure_rolls_back_to_snapshot(fake_model):
    """入队失败：退回触发前的状态（含旧的错误信息），不标 failed。"""
    snapshot = _doc(DocStatus.FAILED, DocStage.EMBEDDING, error_message="TimeoutError: x")
    ok = await DocumentService._enqueue(snapshot, _FakeTask(fail=True))

    assert ok is False
    assert fake_model.updates == [(
        {"id": "docid"},
        {
            "status": DocStatus.FAILED,
            "stage": DocStage.EMBEDDING,
            "error_message": "TimeoutError: x",
        },
    )]
