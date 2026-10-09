"""删文档时清存储单测 —— `_purge_storage` 删原件 + 派生目录，任一步失败都不外抛。

storage 是 document_service 的模块级单例，monkeypatch 成记账的假对象；doc 只用到
三个属性（id / knowledge_base_id / storage_key），用轻量假对象顶替，零 DB 零对象存储。
"""

from types import SimpleNamespace

import pytest

from app.services.knowledge import document_service
from app.services.knowledge.document_service import DocumentService


class _FakeStorage:
    def __init__(self, fail_delete: bool = False, fail_prefix: bool = False) -> None:
        self.fail_delete = fail_delete
        self.fail_prefix = fail_prefix
        self.deleted: list[str] = []
        self.deleted_prefixes: list[str] = []

    async def delete(self, key):
        if self.fail_delete:
            raise ConnectionError("r2 down")
        self.deleted.append(key)

    async def delete_prefix(self, prefix):
        if self.fail_prefix:
            raise ConnectionError("r2 down")
        self.deleted_prefixes.append(prefix)
        return 0


def _doc(storage_key: str = "kb/K/doc/D.pdf"):
    return SimpleNamespace(id="D", knowledge_base_id="K", storage_key=storage_key)


@pytest.mark.parametrize(
    ("fail_delete", "fail_prefix"),
    [(False, False), (True, False), (False, True), (True, True)],
)
async def test_purges_original_and_doc_dir_never_raises(monkeypatch, fail_delete, fail_prefix):
    fs = _FakeStorage(fail_delete=fail_delete, fail_prefix=fail_prefix)
    monkeypatch.setattr(document_service, "storage", fs)

    await DocumentService._purge_storage(_doc())  # 任一步失败都不抛

    # 一步失败不影响另一步照常执行
    assert fs.deleted == ([] if fail_delete else ["kb/K/doc/D.pdf"])
    assert fs.deleted_prefixes == ([] if fail_prefix else ["kb/K/doc/D/"])


async def test_without_storage_key_still_purges_doc_dir(monkeypatch):
    """占位记录（还没回填 storage_key）也要清目录。"""
    fs = _FakeStorage()
    monkeypatch.setattr(document_service, "storage", fs)

    await DocumentService._purge_storage(_doc(storage_key=""))

    assert fs.deleted == []
    assert fs.deleted_prefixes == ["kb/K/doc/D/"]
