"""skill 侧的 agent 装配：把挂载的 skill 变成 middleware + system prompt 片段。

设计稿决策 19/20/22 的落点：
- 工具不自己设计，用 FilesystemMiddleware 自带的 7 个（ls/read_file/write_file/
  edit_file/glob/grep/execute），且**仅当挂了 skill 才装**，没挂一个都不装。
- 不用 SkillsMiddleware，清单 prompt 自己拼。
- 执行后端按 driver 选：LocalShellBackend（不起容器，面向开发者）/ 容器 driver
  （生产）。换 driver 只换这一处，上面两条与 prompt 片段一行不动。
"""

import asyncio
import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence
from uuid import UUID

from deepagents import FilesystemMiddleware
from deepagents.backends import LocalShellBackend
from deepagents.backends.protocol import SandboxBackendProtocol
from langchain_core.tools import BaseTool

from app.core.config import settings
from app.core.storage import storage
from app.models import User
from app.models.skill import Skill
from app.schemas.agent import AgentConfig
from app.services.sandbox.docker_sandbox import DockerSandbox
from app.services.sandbox.layout import SandboxPaths, prepare_workspace_dir, container_paths, pack_skills
from app.services.skill.builtin import resolve_builtin_skills, fetch_builtin_credentials, BuiltinSkill
from app.services.skill.prompt import build_skills_prompt, SkillListing
from app.tools.artifact_fetch import ArtifactFetchTool

logger = logging.getLogger(__name__)

# 单条命令的默认超时与硬上限（秒）。LLM 可为单条命令调高，但不得超过上限 ——
# deepagents 的 max_execute_timeout 默认 3600，一个 skill 脚本跑一小时是失控
# 不是耐心，收到 10 分钟。
# 名字不带下划线是有意的：最外层的工具护栏必须按这个上限单独给 execute 放宽
# （tool_guard._TOOL_TIMEOUT_BUDGETS），两边各写一个数迟早漂移。
EXECUTE_TIMEOUT = 120
EXECUTE_TIMEOUT_CEILING = 600


@dataclass(frozen=True, slots=True)
class SkillMount:
    """（原 docstring 不动）"""

    middleware: FilesystemMiddleware
    paths: SandboxPaths  # 工作区路径，供日志与排查用
    backend: SandboxBackendProtocol  # 收尾要用：docker driver 得把容器销毁掉
    artifact_tools: list[BaseTool]  # 取回历史产物（决策 24）；Playground 无对话实体，为空
    uploaded: dict[UUID, Skill]  # 本轮解出的上传 skill，按 id 索引；prompt_for 据各自 cfg 再筛

    async def close(self) -> None:
        """一轮回复的收尾。docker driver 销毁容器，local driver 无事可做。

        **用 to_thread 而不是直接调**：销毁是一次同步 HTTP，直接调会把事件循环
        卡住那零点几秒，而这时候 SSE 可能还在往前端吐东西。

        故意用 isinstance 而不是 `hasattr(backend, "close")`：将来多一个 driver 时，
        这里会明明白白地要求你想一想它该怎么收尾，而不是靠有没有同名方法蒙混过去。
        """
        if isinstance(self.backend, DockerSandbox):
            await asyncio.to_thread(self.backend.close)

    def _skills_of(self, cfg: AgentConfig) -> list[SkillListing]:
        """这个参与者自己挂的 skill，两种来源合成一份（内置在前）。"""
        mine = [self.uploaded[sid] for sid in cfg.skills if sid in self.uploaded]
        return [*resolve_builtin_skills(cfg.builtin_skills), *mine]

    def has_skills(self, cfg: AgentConfig) -> bool:
        """这个 agent 自己挂了 skill 吗 —— 决定给不给它那 7 个文件工具（决策 19）。

        判「真解出了东西」而不是「字段非空」：配置里可能留着已下架的 skill 名，
        那种情况字段有值、实际无货，不该给工具。
        """
        return bool(self._skills_of(cfg))

    def prompt_for(self, cfg: AgentConfig) -> str:
        """某个参与者的 skill 清单片段 —— 只列它自己挂的，不列同伴的。

        物理上 /skills 底下躺着本轮所有参与者的 skill，但清单各给各的：
        没授予这个成员的技能不该出现在它眼前，否则配置形同虚设。
        """
        return build_skills_prompt(
            self._skills_of(cfg),
            self.paths,
            # artifact_tools 空不空，正是「这条路上有没有取回工具」的唯一真值 ——
            # 不另传标志位，免得两处判断跑偏
            can_fetch=bool(self.artifact_tools),
        )

async def _union_skills(
        cfgs: Sequence[AgentConfig], user: User
) -> tuple[list[BuiltinSkill], list[Skill]]:
    """本轮所有参与者挂的 skill 并集，按首次出现排序。

    去重：两个成员挂了同一个 skill，物料本来就是同一份，铺一份即可 ——
    内置按 name（源目录同一个），上传的按 id（表行同一条）。

    两种来源**分开返回**：内置的下游要的是目录、打成 tar，上传的下游要的是
    zip 字节、直接送进容器解，两条路不同，合成一个列表只会在下游再分一次。

    上传那批的归属校验就是 `created_by=user` 这个查询条件 —— 别人的 id 塞进
    配置也查不出来；查不到的 id 静默跳过，对齐 resolve_builtin_skills 与
    assemble_tools 里知识库那段的容错口径（残留配置不该让整个 agent 起不来）。
    """
    builtin: dict[str, BuiltinSkill] = {}
    for cfg in cfgs:
        for skill in resolve_builtin_skills(cfg.builtin_skills):
            builtin.setdefault(skill.name, skill)

    # dict.fromkeys 去重且保序 —— 顺序决定它们在 prompt 里的排列，应当与用户配的一致
    wanted = list(dict.fromkeys(sid for cfg in cfgs for sid in cfg.skills))
    uploaded: list[Skill] = []
    if wanted:
        rows = await Skill.filter(id__in=wanted, created_by=user)
        by_id = {row.id: row for row in rows}
        uploaded = [by_id[sid] for sid in wanted if sid in by_id]

    return list(builtin.values()), uploaded

async def build_skill_mount(
        cfgs: Sequence[AgentConfig],
        user: User,
        *,
        scope_id: UUID,
        message_id: UUID,
        conversation_id: UUID | None,
        referenced_artifact_ids: frozenset[UUID],
) -> SkillMount | None:
    """据一组 agent config 装出共用的 skill 沙箱；没人挂 skill 返回 None。

    入参是「一组」而非一个：workspace 一轮回复里 supervisor 与各成员同时在场，
    必须共用同一个工作区（决策 12，借还粒度 = 一次完整回复）。Playground 只有
    一个 agent，传 [cfg]。

    并集在本函数里求、不甩给调用方：将来接用户上传的 skill（cfg.skills）时，
    改动收在这里，两条调用路径一行不动。

    Args:
        cfgs: 本轮全部参与者的 config
        scope_id: 工作区目录的归属键。workspace 对话传 workspace_id（跨对话保留，
            决策 14）；Playground 是试跑场、不属于任何 workspace，传 user_id。
        message_id: 本轮消息 ID，用作交付区目录名
        conversation_id: 本对话 ID，决定 fetch 工具能取回哪些历史产物（决策 24）。
            Playground 传 None —— 它的消息不入库、产物没有对话归属，「本对话」
            在那边不存在，故不给这个工具（决策 26）。同样刻意不给默认值：
            漏传的话签名对、不报错，只是取回能力静默消失。
        referenced_artifact_ids: 本对话历史里被用户拖进来引用过的产物 id（决策 25），
            并进 fetch 工具的取值范围 —— 它们属于别的对话，光靠 conversation_id
            那个条件够不着。**同样刻意不给默认值**，漏传只会让用户拖进来的文件
            下一轮取不回来，而这事不报错。
    """
    mounted, uploaded = await _union_skills(cfgs, user)
    if not mounted and not uploaded:
        return None

    credentials = await fetch_builtin_credentials(user, [s.name for s in mounted])
    skill_dirs = [s.directory for s in mounted]

    if settings.SANDBOX_DRIVER == "docker":
        skill_zips = await _fetch_skill_archives(uploaded)
        paths, backend = _docker_backend(skill_dirs, skill_zips, credentials, message_id)
    elif settings.SANDBOX_DRIVER == "local":
        if uploaded:
            logger.warning("local driver 不支持用户上传的 skill，本轮跳过 %d 个", len(uploaded))
        paths, backend = _local_backend(skill_dirs, credentials, scope_id, message_id)
    else:
        # 配错了就当场炸，不要悄悄退回某一档 —— 「以为在跑容器、其实在宿主机上裸跑」
        # 是这个模块最不能出的错
        raise ValueError(f"SANDBOX_DRIVER 只能是 local 或 docker，当前是 {settings.SANDBOX_DRIVER!r}")

    # 取回历史产物的工具：绑本轮的 backend（只有它够得着工作区）与本对话。
    # Playground 没有对话实体，这里为空 —— 它拿到的仍是那 7 个文件工具，
    # 只是跨轮取回这件事在那边不存在（决策 26）
    artifact_tools: list[BaseTool] = (
        [
            ArtifactFetchTool(
                backend=backend,
                workspace_dir=paths.workspace,
                conversation_id=conversation_id,
                user_id=user.id,
                referenced_artifact_ids=referenced_artifact_ids,
            )
        ]
        if conversation_id is not None
        else []
    )

    return SkillMount(
        middleware=FilesystemMiddleware(
            backend=backend,
            max_execute_timeout=EXECUTE_TIMEOUT_CEILING,
        ),
        paths=paths,
        backend=backend,
        artifact_tools=artifact_tools,
        uploaded={s.id: s for s in uploaded},
    )


async def _fetch_skill_archives(skills: Sequence[Skill]) -> list[tuple[str, bytes]]:
    """并发把上传的 skill 包从对象存储读回来。

    单个读失败只跳过它 —— 一个包丢了不该让整轮回复挂掉，对齐 assemble_tools
    里「MCP 单 server 失败跳过」的口径。
    """
    if not skills:
        return []

    results = await asyncio.gather(
        *(storage.read(s.storage_key) for s in skills), return_exceptions=True
    )

    archives: list[tuple[str, bytes]] = []
    for skill, result in zip(skills, results):
        if isinstance(result, BaseException):
            logger.warning("skill %s 的包读不出来，本轮跳过：%s", skill.name, result)
            continue
        archives.append((skill.name, result))
    return archives


def _docker_backend(
        skill_dirs: list[Path],
        skill_zips: list[tuple[str, bytes]],
        credentials: dict[str, str],
        message_id: UUID,
) -> tuple[SandboxPaths, DockerSandbox]:
    """生产 driver：一次性容器，起容器的动作推迟到第一次真用到（决策 22a）。

    这里没有 scope_id —— docker 那条路上「哪个 workspace」不由路径承载，
    由对象存储的 key 承载（决策 14）。
    """
    paths = container_paths(message_id)
    backend = DockerSandbox(
        paths=paths,
        skill_tar=pack_skills(skill_dirs, skill_zips),
        env=credentials,  # 容器的 PATH / HOME 由镜像给，不需要 _sandbox_env 那套
        timeout=EXECUTE_TIMEOUT,
        max_timeout=EXECUTE_TIMEOUT_CEILING,
    )
    return paths, backend


def _local_backend(
        skill_dirs: list[Path], credentials: dict[str, str], scope_id: UUID, message_id: UUID
) -> tuple[SandboxPaths, LocalShellBackend]:
    """开发者 driver：不起容器，直接在宿主机目录上跑（决策 18）。

    **它不冒充隔离**：跑的是 clone 项目那个人自己的东西，边界靠的是「你信任
    自己挂的 skill」，不是任何技术手段。
    """
    paths = prepare_workspace_dir(scope_id, skill_dirs, message_id=message_id)
    backend = LocalShellBackend(
        root_dir=paths.root,
        # virtual_mode=False：文件工具与 execute 必须共用同一个路径空间。
        # 开虚拟根只骗得过文件工具 —— shell 由操作系统解释，照样按宿主机真实
        # 路径找文件，两半会打架（实测 execute 报 can't open file '/skills/...'）。
        # 它也从来不是安全边界，deepagents 自己的告警原话：
        # "virtual_mode does not restrict shell execution"。
        virtual_mode=False,
        timeout=EXECUTE_TIMEOUT,
        env={**credentials, **_sandbox_env(paths)},
        inherit_env=False,  # 显式写出：宿主机环境（DB 密码 / R2 密钥）绝不外泄
    )
    return paths, backend


def _sandbox_env(paths: SandboxPaths) -> dict[str, str]:
    """沙箱进程的环境变量白名单 —— 这是 docker run -e 的本地等价物。

    带 key 的 skill 将来把解密后的凭据并进这里（决策 15）。
    """
    return {
        # 空 PATH 会让 python3 都找不到。带上当前解释器所在目录，保证脚本跑得起来；
        # 这是 LocalShell driver 专有的：容器 driver 的 PATH 由镜像决定，不走这里。
        "PATH": os.pathsep.join(
            [str(Path(sys.executable).parent), os.defpath.lstrip(os.pathsep)]
        ),
        "HOME": paths.workspace,  # 别让脚本写进真的家目录
        "LANG": "C.UTF-8",
        "PYTHONIOENCODING": "utf-8",  # 中文标签的图表，输出不因终端编码而乱
        "PYTHONDONTWRITEBYTECODE": "1",  # 不在 skills/ 里拉 __pycache__
    }
