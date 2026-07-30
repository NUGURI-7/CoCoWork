"""沙箱工作区的目录布局。

容器里的形态（设计稿 C.1）：
    /skills                投进去的 skill，只读
    /workspace             工作台：铺入**本对话**的历史产物，跨对话的给模型工具按需取（决策 14a）
    /outputs/<message_id>  交付区：每轮新建的空目录，放进来的才是产物
    /tmp                   本轮草稿（execute 的工作目录），销毁即弃

本模块管两个 driver 的路径：LocalShell 在宿主机目录上镜像同一套布局
（prepare_workspace_dir，要真建目录，**三个目录每轮重铺**），LocalDocker
直接给容器内的固定路径（container_paths，什么都不建）。

布局两边保持一致，是为了 prompt 里的路径、SKILL.md 里写的相对路径一个字
都不用改 —— 换 driver 换掉的只有 backend 实现。
"""
import io
import shutil
import tarfile
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from app.core.config import settings


def _drop_pycache(info: tarfile.TarInfo) -> tarfile.TarInfo | None:
    """打包时剔掉 __pycache__ / *.pyc（返回 None 即丢弃该条目）。

    与本地那份的 ignore_patterns 同义：送进去的是源码，不是宿主机上跑出来的字节码
    —— 架构不一定一样，带过去只会添乱。
    """
    if "__pycache__" in info.name or info.name.endswith(".pyc"):
        return None
    return info


def pack_skill_dirs(skill_dirs: Sequence[Path]) -> bytes:
    """把 skill 源目录打成一个 tar，供 docker driver 灌进容器的 /skills。

    这是 prepare_workspace_dir 里那句 copytree 的对应物：同样是「把物料摆进去」，
    只是本地摆的是宿主机目录，容器摆的是一包字节（决策 21a / C.3）。

    成员名以 skill 目录名开头（`svg-chart/SKILL.md`），解在 /skills 上就落成
    `/skills/svg-chart/SKILL.md` —— 与本地布局逐字一致，SKILL.md 里的相对路径
    两边都不用改。
    """
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tar:
        for src in skill_dirs:
            # 目标目录名 = 源目录名，与本地那份同一条规矩：源目录已是校验过的
            # 规范形态，照搬即可，别拿 frontmatter 的 name 另起一个
            tar.add(src, arcname=src.name, filter=_drop_pycache)
    return buf.getvalue()


@dataclass(frozen=True, slots=True)
class SandboxPaths:
    """一次运行里，**模型看到的**目录路径。值由 driver 决定，不是常量。

    本地 driver   → <root>/skills、<root>/workspace、<root>/outputs/<mid>、<root>/tmp
    docker driver → /skills、/workspace、/outputs/<mid>、/tmp

    为什么不能统一成 /skills：deepagents 的文件工具与 execute **共用一个路径空间**
    （其自带 prompt 明写 "All file paths must start with a /"），本地没法把
    <root>/skills 伪装成 /skills —— virtual_mode 只骗得过文件工具、骗不过 shell。
    """

    root: str
    skills: str
    workspace: str
    outputs: str
    tmp: str


def prepare_workspace_dir(
        scope_id: UUID,
        skill_dirs: Sequence[Path],
        *,
        message_id: UUID,
) -> SandboxPaths:
    """铺好一次运行所需的工作区目录，返回它的根。

    Args:
        scope_id: 工作区 ID，决定目录挂在哪一支下面。**它不再意味着「跨对话可见」**
            —— 目录每轮重铺，跨对话的延续性只由对象存储承载（决策 14a 改判）。
            该值只能由服务端从 DB 取，绝不接受来自 LLM 或 skill 的输入 ——
            它是这层唯一的安全边界。
        skill_dirs: 要投进去的 skill 源目录，每个都是「一目录一 skill」的规范形态
        message_id: 本轮回复的消息 ID，用作交付区目录名。同样只能服务端生成 ——
            一旦可由外部指定，就成了「传谁的 id 读谁的产物」。
    Returns:
        工作区根目录的绝对路径，即 LocalShellBackend 的 root_dir
    """
    root = settings.sandbox_local_path / str(scope_id)

    # 三个目录每次整个重铺，真相都不在这儿，删干净不丢东西。
    # **workspace 也在内**（2026-07-29 决策 14a 改判）：它原本「只保证存在、绝不清空」，
    # 于是宿主机上跨轮跨对话一直堆着 —— 而 docker driver 每轮都是全新空 tmpfs。
    # 两个 driver 语义不同的代价不是「不一致」这么抽象：本地调试时文件永远「自己就在」，
    # fetch 工具一次都不会被触发，等部署到 docker 才发现模型不会用它 ——
    # **开发环境把 bug 藏起来了**。清空是安全的：产物早已被 collect_artifacts
    # 收进对象存储，两个 driver 走的是同一条收集路径。
    for name in ("skills", "workspace", "tmp"):
        target = root / name
        if target.exists():
            shutil.rmtree(target)
        target.mkdir(parents=True)

    for src in skill_dirs:
        # 目标目录名 = 源目录名。规范要求 name 等于父目录名，而源目录已是
        # 校验过的规范形态，照搬即可，不要拿 frontmatter 的 name 另起一个。
        shutil.copytree(
            src,
            root / "skills" / src.name,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
        )
    # 交付区 = 本轮专属的空目录。**刻意不加 exist_ok** —— message_id 每轮唯一，
    # 目录已存在只可能是同一个 id 被用了两次，那是 bug；宁可当场炸，也不能让
    # 上一轮的残留混进这一轮的产物清单（识别机制的全部前提就是「这个目录是空的」）。
    outputs = root / "outputs" / str(message_id)
    outputs.mkdir(parents=True)

    return SandboxPaths(
        root=str(root),
        skills=str(root / "skills"),
        workspace=str(root / "workspace"),
        outputs=str(outputs),
        tmp=str(root / "tmp"),
    )


def container_paths(message_id: UUID) -> SandboxPaths:
    """docker driver 的那一份路径 —— 容器内的固定位置。

    与 prepare_workspace_dir 的**根本区别是它什么也不创建**：四个目录都是容器
    启动时就挂好的 tmpfs，宿主机上一个字节都不落。所以这里没有 scope_id
    ——「哪个 workspace」在 docker 那条路上不由路径承载，而是由对象存储的
    key 承载（决策 14：持久化的是产物，容器与工作区随时可销毁）。

    唯一需要现建的是交付区 /outputs/<message_id>，它由 DockerSandbox 在起完
    容器后 mkdir。本地那份特意不加 exist_ok（撞 id 就当场炸），容器这边这层
    保护是白送的：/outputs 每轮都是全新的空 tmpfs，不可能有上一轮的残留。
    """
    return SandboxPaths(
        root="/",
        skills="/skills",
        workspace="/workspace",
        outputs=f"/outputs/{message_id}",
        tmp="/tmp",
    )
