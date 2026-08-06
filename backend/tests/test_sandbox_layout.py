"""沙箱目录布局单测 —— 零 docker、零 DB、零网络。

守的规矩：
- 每轮工作区**真的**是空的（决策 14a 改判后最容易被悄悄破坏的一条：
  谁把 workspace 从清空名单里去掉，本地开发照样跑，只有部署到容器才发现
  模型不会用 fetch 工具 —— 开发环境把 bug 藏起来了）
- 交付区撞名当场炸（产物识别的全部前提是「这个目录是空的」）
- 送进容器的 skill 里不夹带宿主机跑出来的字节码
"""

import tarfile
import io
from pathlib import Path
from uuid import uuid4

import pytest

from app.core.config import settings
from app.services.sandbox.layout import (
    container_paths,
    pack_skills,
    prepare_workspace_dir,
)


@pytest.fixture
def sandbox_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """把沙箱根挪到临时目录 —— 绝对路径会被 _under_base 原样返回。"""
    root = tmp_path / "sandbox"
    monkeypatch.setattr(settings, "SANDBOX_LOCAL_ROOT", str(root))
    return root


def _make_skill(base: Path, name: str) -> Path:
    """造一个规范形态的 skill 目录，顺带塞进宿主机跑出来的字节码。"""
    d = base / name
    (d / "scripts").mkdir(parents=True)
    (d / "SKILL.md").write_text(f"---\nname: {name}\n---\n正文", encoding="utf-8")
    (d / "scripts" / "bar.py").write_text("print(1)", encoding="utf-8")
    (d / "scripts" / "__pycache__").mkdir()
    (d / "scripts" / "__pycache__" / "bar.cpython-313.pyc").write_bytes(b"\x00binary")
    return d


# ---------- pack_skills：打给容器的那包 ----------

def test_pack_skills_uses_dir_name_as_prefix(tmp_path: Path):
    """成员名以 skill 目录名开头，解在 /skills 上就落成 /skills/<name>/…

    这条钉死的是「本地布局与容器布局逐字一致」——SKILL.md 里写的相对路径
    两边都不用改，正是靠它。
    """
    tar_bytes = pack_skills([_make_skill(tmp_path, "svg-chart")])

    with tarfile.open(fileobj=io.BytesIO(tar_bytes)) as tar:
        names = tar.getnames()

    assert "svg-chart/SKILL.md" in names
    assert "svg-chart/scripts/bar.py" in names


def test_pack_skills_drops_pycache(tmp_path: Path):
    """__pycache__ / *.pyc 一个都不许进去 —— 宿主机与容器架构未必一样。"""
    tar_bytes = pack_skills([_make_skill(tmp_path, "svg-chart")])

    with tarfile.open(fileobj=io.BytesIO(tar_bytes)) as tar:
        names = tar.getnames()

    assert not [n for n in names if "__pycache__" in n or n.endswith(".pyc")]


def test_pack_skills_packs_all_of_them(tmp_path: Path):
    """多个 skill 打一包 —— 一轮回复里全场参与者共用一个工作区（决策 12）。"""
    dirs = [_make_skill(tmp_path, "svg-chart"), _make_skill(tmp_path, "pdf-fill")]
    tar_bytes = pack_skills(dirs)

    with tarfile.open(fileobj=io.BytesIO(tar_bytes)) as tar:
        names = tar.getnames()

    assert "svg-chart/SKILL.md" in names
    assert "pdf-fill/SKILL.md" in names


# ---------- prepare_workspace_dir：本地 driver 的那套目录 ----------

def test_prepare_lays_out_four_places(sandbox_root: Path, tmp_path: Path):
    """四个位置都在，且路径与返回的 SandboxPaths 对得上。"""
    scope, mid = uuid4(), uuid4()
    paths = prepare_workspace_dir(scope, [_make_skill(tmp_path, "svg-chart")], message_id=mid)

    assert Path(paths.skills, "svg-chart", "SKILL.md").is_file()
    assert Path(paths.workspace).is_dir()
    assert Path(paths.tmp).is_dir()
    assert Path(paths.outputs).is_dir()
    assert Path(paths.outputs).name == str(mid)  # 交付区目录名 = 本轮 message_id


def test_prepare_wipes_workspace_every_turn(sandbox_root: Path, tmp_path: Path):
    """**每轮清空工作区**（决策 14a）—— 本片最怕被人「顺手改回去」的一条。

    不清的话本地开发时文件永远「自己就在」，fetch 工具一次都不会被触发，
    等部署到 docker（每轮全新空 tmpfs）才发现模型压根不会用它。
    """
    scope = uuid4()
    skill = _make_skill(tmp_path, "svg-chart")

    first = prepare_workspace_dir(scope, [skill], message_id=uuid4())
    Path(first.workspace, "上一轮留下的.txt").write_text("旧", encoding="utf-8")
    Path(first.tmp, "草稿.json").write_text("旧", encoding="utf-8")

    second = prepare_workspace_dir(scope, [skill], message_id=uuid4())

    assert list(Path(second.workspace).iterdir()) == []
    assert list(Path(second.tmp).iterdir()) == []


def test_prepare_rejects_duplicate_message_id(sandbox_root: Path, tmp_path: Path):
    """交付区撞名当场炸，不 exist_ok。

    产物识别的全部前提是「这个目录一开始是空的」；同一个 message_id 被用两次
    只可能是 bug，静静复用会让上一轮的残留混进这一轮的产物清单。
    """
    scope, mid = uuid4(), uuid4()
    skill = _make_skill(tmp_path, "svg-chart")
    prepare_workspace_dir(scope, [skill], message_id=mid)

    with pytest.raises(FileExistsError):
        prepare_workspace_dir(scope, [skill], message_id=mid)


def test_prepare_keeps_other_scopes_untouched(sandbox_root: Path, tmp_path: Path):
    """清的是自己那一支，别的 workspace 不受牵连。"""
    skill = _make_skill(tmp_path, "svg-chart")
    a = prepare_workspace_dir(uuid4(), [skill], message_id=uuid4())
    Path(a.workspace, "甲的文件.txt").write_text("在", encoding="utf-8")

    prepare_workspace_dir(uuid4(), [skill], message_id=uuid4())

    assert Path(a.workspace, "甲的文件.txt").is_file()


# ---------- container_paths：docker driver 的那套 ----------

def test_container_paths_are_fixed_and_create_nothing(tmp_path: Path):
    """容器内路径是固定值，且这个函数什么都不建（四个目录是挂好的 tmpfs）。"""
    mid = uuid4()
    paths = container_paths(mid)

    assert (paths.skills, paths.workspace, paths.tmp) == ("/skills", "/workspace", "/tmp")
    assert paths.outputs == f"/outputs/{mid}"
    assert list(tmp_path.iterdir()) == []
