"""文件进出容器的 tar 打包 / 拆包单测（docker_sandbox 的两个纯函数）。

这条路是 2026-07-28 实测推翻 `docker cp` 之后才有的（C.3）：四个可写目录全是
tmpfs，而 docker 的 cp 接口够不着 tmpfs。字节改走 exec 的 stdin/stdout，
打包拆包就成了我们自己的责任 —— 也就成了该被钉住的东西。
"""

import io
import tarfile

import pytest

from app.services.sandbox.docker_sandbox import _pack_tar, _unpack_single


def _members(tar_bytes: bytes) -> list[tarfile.TarInfo]:
    with tarfile.open(fileobj=io.BytesIO(tar_bytes)) as tar:
        return list(tar)


# ---------- _pack_tar ----------

def test_pack_strips_leading_slash():
    """tar 不收绝对路径；解包时以 / 为根，成员名必须是相对的。"""
    members = _members(_pack_tar([("/workspace/sales.csv", b"a,b\n1,2\n")]))

    assert [m.name for m in members] == ["workspace/sales.csv"]


def test_pack_emits_no_directory_entries():
    """**只放文件条目**。

    /skills /workspace /outputs /tmp 都是已经挂好的 tmpfs，带上目录条目会让
    tar 去改这些挂载点的权限与属主，在 --user nobody 下多半直接失败。
    缺的中间层 tar 解包时自己会建。
    """
    members = _members(
        _pack_tar([("/workspace/a/b/deep.txt", b"x"), ("/workspace/top.txt", b"y")])
    )

    assert all(m.isfile() for m in members)
    assert [m.name for m in members] == ["workspace/a/b/deep.txt", "workspace/top.txt"]


def test_pack_records_real_size_and_content():
    """大小与内容原样进包 —— 二进制不被任何编码碰过。"""
    blob = bytes(range(256))
    with tarfile.open(fileobj=io.BytesIO(_pack_tar([("/tmp/blob.bin", blob)]))) as tar:
        member = tar.getmember("tmp/blob.bin")
        assert member.size == len(blob)
        assert tar.extractfile(member).read() == blob


def test_pack_sets_readable_mode():
    """0644：容器里跑 skill 的是 nobody，读不到就白送了。"""
    assert _members(_pack_tar([("/skills/x.py", b"print()")]))[0].mode == 0o644


# ---------- _unpack_single ----------

def test_unpack_returns_the_only_file():
    """下载接口一次只取一个文件，拿到第一个普通文件就够。"""
    assert _unpack_single(_pack_tar([("/outputs/1/chart.svg", b"<svg/>")])) == b"<svg/>"


def test_unpack_skips_directory_entries():
    """容器里 `tar -c` 出来的包可能带目录条目，别把目录当文件读。"""
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tar:
        info = tarfile.TarInfo("outputs")
        info.type = tarfile.DIRTYPE
        tar.addfile(info)
        payload = tarfile.TarInfo("outputs/chart.svg")
        payload.size = 6
        tar.addfile(payload, io.BytesIO(b"<svg/>"))

    assert _unpack_single(buf.getvalue()) == b"<svg/>"


def test_unpack_raises_on_empty_archive():
    """空包 = 那个文件没取到。抛出去由调用方翻成 error 字段，别返回空字节
    冒充「文件是空的」—— 两者对模型的意思完全不同。"""
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w"):
        pass

    with pytest.raises(ValueError):
        _unpack_single(buf.getvalue())
