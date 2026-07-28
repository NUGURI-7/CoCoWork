"""沙箱工作区的目录布局。

容器里的形态（设计稿 C.1）：
    /skills                投进去的 skill，只读
    /workspace             工作台：容器启动时铺入历史产物，跨对话可见
    /outputs/<message_id>  交付区：每轮新建的空目录，放进来的才是产物
    /tmp                   本轮草稿（execute 的工作目录），销毁即弃

本模块是 **LocalShell driver** 的那一份实现：不起容器，在宿主机目录上镜像
同一套布局（决策 18 —— LocalShell 面向 clone 项目的开发者，不装 docker 也能
跑通整条 skill 链路；生产走 LocalDocker）。

布局两边保持一致，是为了 prompt 里的路径、SKILL.md 里写的相对路径一个字
都不用改 —— 换 driver 换掉的只有 backend 实现。
"""

import shutil
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from app.core.config import settings


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
        scope_id: 工作区 ID。目录绑 workspace 而非对话，故跨对话可见
            （设计稿决策 14）。该值只能由服务端从 DB 取，绝不接受来自
            LLM 或 skill 的输入 —— 它是这层唯一的安全边界。
        skill_dirs: 要投进去的 skill 源目录，每个都是「一目录一 skill」的规范形态
        message_id: 本轮回复的消息 ID，用作交付区目录名。同样只能服务端生成 ——
            一旦可由外部指定，就成了「传谁的 id 读谁的产物」。
    Returns:
        工作区根目录的绝对路径，即 LocalShellBackend 的 root_dir
    """
    root = settings.sandbox_local_path / str(scope_id)

    # skills/ 与 tmp/ 每次整个重铺：前者是投递进去的物料，后者是本轮草稿。
    # 两者的真相都不在这儿，删干净不丢东西。
    for name in ("skills", "tmp"):
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
    # workspace/ 只保证存在，绝不清空 —— 装的是 agent 跨对话积累下来的东西
    (root / "workspace").mkdir(parents=True, exist_ok=True)

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
