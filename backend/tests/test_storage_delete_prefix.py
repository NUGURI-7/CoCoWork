"""Storage.delete_prefix 单测 —— 本地盘实现 + 前缀校验，落在 tmp_path，不碰真实存储根。

断言三件事：前缀下的文件全删且返回个数对、「目录」边界不误删兄弟（`doc/2/` 不碰
`doc/23/`）、危险前缀（空串 / 根 / 不带结尾斜杠 / 解析后指向根）一律拒绝。
R2 实现走 boto3 分页 + 批量删除，要真桶才有意义，不在这里测。
"""

import pytest

from app.core.storage.local import LocalStorage


@pytest.fixture
def local(tmp_path):
    store = LocalStorage()
    store._root = tmp_path.resolve()
    return store


def _touch(store: LocalStorage, key: str) -> None:
    path = store._root / key
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x")


async def test_deletes_everything_under_prefix(local):
    for key in ["kb/1/doc/2.pdf", "kb/1/doc/2/figures/a/1.png", "kb/1/doc/2/figures/a/2.png"]:
        _touch(local, key)

    assert await local.delete_prefix("kb/1/doc/2/") == 2
    assert not (local._root / "kb/1/doc/2").exists()
    # 原件不在这个「目录」里，按前缀删不该碰它
    assert (local._root / "kb/1/doc/2.pdf").exists()


async def test_does_not_touch_sibling_with_same_leading_chars(local):
    _touch(local, "kb/1/doc/2/figures/1.png")
    _touch(local, "kb/1/doc/23/figures/1.png")

    await local.delete_prefix("kb/1/doc/2/")
    assert (local._root / "kb/1/doc/23/figures/1.png").exists()


async def test_missing_prefix_is_noop(local):
    assert await local.delete_prefix("kb/404/") == 0


@pytest.mark.parametrize("prefix", ["", "/", "//", "kb/1/doc/2"])
async def test_rejects_unsafe_prefix(local, prefix):
    with pytest.raises(ValueError):
        await local.delete_prefix(prefix)


async def test_rejects_prefix_resolving_to_root(local):
    _touch(local, "kb/1/doc/2.pdf")
    with pytest.raises(ValueError):
        await local.delete_prefix("kb/../")
    assert (local._root / "kb/1/doc/2.pdf").exists()
