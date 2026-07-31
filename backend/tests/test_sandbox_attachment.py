"""拖引用附件的单测（决策 25）—— 灌工作区那一段，零 docker 零对象存储。

`resolve_refs` 要查库，不在这一批（那是集成测试的活）。这里考的是它下游：
撞名怎么改、字节送不到时说什么、给模型的那行标注长什么样。

**为什么标注的文字值得写断言**：它是模型判断「文件在不在、在哪」的唯一依据。
路径写错、失败说成成功，模型就会拿着不存在的文件一路往下走 —— 而那种错
在日志里安安静静，只在回复里显形。
"""

from uuid import uuid4

import pytest

from app.models.sandbox import SandboxArtifact
from app.services.sandbox import attachment
from app.services.sandbox.attachment import (
    _unique_name,
    describe_unavailable,
    inject_attachments,
)
from app.services.sandbox.layout import container_paths
from tests.sandbox_fakes import FakeBackend, FakeStorage

PATHS = container_paths(uuid4())


def _artifact(filename: str, size: int = 12345, key: str | None = None) -> SandboxArtifact:
    """脱库造一行产物 —— 只用到展示字段与 storage_key，不落库。"""
    return SandboxArtifact(
        id=uuid4(),
        filename=filename,
        size=size,
        content_type="text/csv",
        storage_key=key or f"sandbox/ws/mid/{filename}",
    )


# ---------- _unique_name：同批撞名 ----------

@pytest.mark.parametrize(
    ("existing", "name", "expected"),
    [
        (set(), "chart.svg", "chart.svg"),
        ({"chart.svg"}, "chart.svg", "chart-2.svg"),
        ({"chart.svg", "chart-2.svg"}, "chart.svg", "chart-3.svg"),
        ({"README"}, "README", "README-2"),  # 没有扩展名
        ({".env"}, ".env", ".env-2"),  # 纯扩展名，整个当主干
        ({"a.tar.gz"}, "a.tar.gz", "a.tar-2.gz"),  # 只切最后一个点，够用
    ],
)
def test_unique_name(existing: set[str], name: str, expected: str):
    assert _unique_name(existing, name) == expected


# ---------- inject_attachments：正常路径 ----------

async def test_no_attachments_returns_empty_string():
    """没附件就没标注 —— 调用方按空串跳过，不必先判断。"""
    assert await inject_attachments(FakeBackend(), PATHS, []) == ""


async def test_injects_bytes_and_reports_absolute_path(monkeypatch: pytest.MonkeyPatch):
    """字节进工作区，标注给**绝对路径** —— 模型照着这个路径就能 execute。"""
    art = _artifact("sales.csv")
    backend = FakeBackend()
    monkeypatch.setattr(
        attachment, "storage", FakeStorage({art.storage_key: b"a,b\n1,2\n"})
    )

    note = await inject_attachments(backend, PATHS, [art])

    assert backend.uploaded == [("/workspace/sales.csv", b"a,b\n1,2\n")]
    assert note == "<attachments>用户附上的文件，已放入工作区：/workspace/sales.csv (8B)。</attachments>"


async def test_reports_actual_byte_count_not_the_db_column(monkeypatch: pytest.MonkeyPatch):
    """报的是真写进去那份的大小，不是库里那个数（两者理论上相等，
    但模型该看到的是工作区里现在那份）。"""
    art = _artifact("sales.csv", size=999999)  # 库里记的是假的
    monkeypatch.setattr(attachment, "storage", FakeStorage({art.storage_key: b"xx"}))

    assert "(2B)" in await inject_attachments(FakeBackend(), PATHS, [art])


async def test_same_filename_from_two_conversations_gets_suffixed(
        monkeypatch: pytest.MonkeyPatch,
):
    """两个对话各自产过 chart.svg，一起拖进来 —— 后一个不许覆盖前一个。

    覆盖等于悄悄吞掉一个用户明确附上的文件，比报错更糟。
    """
    a, b = _artifact("chart.svg", key="k-a"), _artifact("chart.svg", key="k-b")
    backend = FakeBackend()
    monkeypatch.setattr(
        attachment, "storage", FakeStorage({"k-a": b"<svg>A</svg>", "k-b": b"<svg>B</svg>"})
    )

    note = await inject_attachments(backend, PATHS, [a, b])

    assert [p for p, _ in backend.uploaded] == [
        "/workspace/chart.svg",
        "/workspace/chart-2.svg",
    ]
    assert "/workspace/chart.svg" in note and "/workspace/chart-2.svg" in note


async def test_one_batch_one_round_trip(monkeypatch: pytest.MonkeyPatch):
    """多个附件一趟送完 —— 每趟往返约 0.68s（设计稿 §5 实测），按文件拆开会成倍放大。"""
    arts = [_artifact(f"f{i}.txt", key=f"k{i}") for i in range(3)]
    calls: list[int] = []

    class CountingBackend(FakeBackend):
        async def aupload_files(self, files):
            calls.append(len(files))
            return await super().aupload_files(files)

    monkeypatch.setattr(
        attachment, "storage", FakeStorage({f"k{i}": b"x" for i in range(3)})
    )
    await inject_attachments(CountingBackend(), PATHS, arts)

    assert calls == [3]


# ---------- inject_attachments：坏路径 ----------

async def test_unreadable_blob_is_reported_not_raised(monkeypatch: pytest.MonkeyPatch):
    """库里有行、存储里没字节 —— 说清楚，别炸掉整轮回复。"""
    ok, bad = _artifact("good.csv", key="k-ok"), _artifact("gone.csv", key="k-bad")
    monkeypatch.setattr(
        attachment, "storage", FakeStorage({"k-ok": b"x"}, broken={"k-bad"})
    )

    note = await inject_attachments(FakeBackend(), PATHS, [ok, bad])

    assert "/workspace/good.csv" in note
    assert "没能放进工作区" in note and "gone.csv" in note


async def test_upload_error_lands_in_the_failed_segment(monkeypatch: pytest.MonkeyPatch):
    """字节读到了但送不进容器，同样如实说。"""
    art = _artifact("sales.csv", key="k")
    monkeypatch.setattr(attachment, "storage", FakeStorage({"k": b"x"}))
    backend = FakeBackend(upload_errors=["容器没响应"])

    note = await inject_attachments(backend, PATHS, [art])

    assert "已放入工作区" not in note
    assert "没能放进工作区" in note and "sales.csv" in note


async def test_upload_blowing_up_entirely_still_returns_a_note(
        monkeypatch: pytest.MonkeyPatch,
):
    """整批上传抛异常也不往外扔 —— 模型收到标注还能换个做法接着走。"""
    art = _artifact("sales.csv", key="k")
    monkeypatch.setattr(attachment, "storage", FakeStorage({"k": b"x"}))
    backend = FakeBackend(upload_raises=RuntimeError("沙箱没了"))

    note = await inject_attachments(backend, PATHS, [art])

    assert "没能放进工作区" in note and "sales.csv" in note


# ---------- describe_unavailable：压根没有沙箱那一档 ----------

def test_describe_unavailable_states_the_files_and_the_reason():
    """没人挂 skill 时**不报错**（2026-07-30 用户拍板）：消息照发，
    但绝不能让模型以为文件在工作区里。"""
    note = describe_unavailable([_artifact("sales.csv")])

    assert "sales.csv (12KB)" in note
    assert "/workspace" not in note  # 没放进去，就一个路径都不许给
    assert "读不到" in note


# ---------- 决策 26：Playground 不接这套 ----------

async def test_playground_rejects_artifact_refs():
    """Playground 的消息不入库、产物 conversation_id 为 NULL，「本对话」在那边
    根本不存在。与其编一个近似答案，不如当场说不支持。

    守卫必须排在一切 IO 之前 —— 这条用例连 DB 都没连上就该过，
    它同时也证明了这一点（真去查库会当场报连接错误）。
    """
    from app.agents.runtime.runner import prepare_stream
    from app.agents.runtime.spec import AgentSpec
    from app.core.exceptions import ValidationException
    from app.schemas.agent.chat_schema import ArtifactRefBlock, ChatStreamRequest
    from app.schemas.agent.config_schema import AgentConfig

    request = ChatStreamRequest(
        content=[ArtifactRefBlock(artifact_id=uuid4(), filename="sales.csv", size=1)]
    )
    spec = AgentSpec(template="general", config=AgentConfig())

    with pytest.raises(ValidationException, match="Playground"):
        await prepare_stream(spec, request, None, message_id=uuid4())
