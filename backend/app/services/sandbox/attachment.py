"""拖进输入框的产物引用 —— 把用户指定的历史产物送进本轮工作区（决策 25）。

与 fetch_artifact 工具（决策 24）的分野照抄 OpenAI 的两条路：
- **人指定的**（本模块）= File Inputs：用户从产出物面板把卡片拖进输入框，
  后端直接把字节灌进 /workspace，模型不必调工具就看得见。
- **模型自己找的**（artifact_fetch.py）= File Search：模型在历史的 <artifacts>
  标注里看见文件名，想用了才去取。
两者不冲突，真实产品都是两样都有。本模块只管前者。

**字节不经过浏览器**：拖的是「已经在对象存储里的产物」，不是本地文件 ——
前端从头到尾只传一个 artifact_id。于是 PDF / 图片 / xlsx 原样保真是白捡的
（字节压根没被碰过），也不涉及 multipart。

**刻意不按对话过滤**：跨对话正是这个功能的全部意义 —— 产物绑 workspace 不绑
对话，右栏面板本来就把整个工作空间的产出摊在那儿，拖哪条都该成立。
边界只有一条：归属人是不是你（进 WHERE，不进 if）。

一次拖引用走两趟，中间隔着「沙箱装配」这道坎：

    resolve_refs   拿 id 查库、校归属、回填文件名与大小 → 结果落进 user 消息
         ↓         （必须赶在落库之前问：引用无效就 404，且这句话不落库）
    装配沙箱        到这一步才知道工作区在哪 —— 容器内是 /workspace，
         ↓          本地 driver 是宿主机上某个目录，路径由 driver 决定
  inject_attachments 按 storage_key 读字节 → 灌进工作区 → 返回给模型看的那行标注

分两趟不是为了好看。字节得等工作区存在才有地方放；而「这引用作数吗」必须
在落库之前问 —— 合成一趟就得把落库推到装配之后，装配一报错（模型没配、
容器起不来），用户刚说的那句话就蒸发了。这条端点从 d-1 起就定死
「说出去的话即事实，先落库」。
"""

import logging
from collections.abc import Sequence
from uuid import UUID

from deepagents.backends.protocol import SandboxBackendProtocol

from app.core.exceptions import NotFound404, ValidationException
from app.core.storage import storage
from app.models import User
from app.models.sandbox import SandboxArtifact
from app.schemas.agent.chat_schema import ArtifactRefBlock, ContentBlock
from app.services.sandbox.artifact import human_size
from app.services.sandbox.layout import SandboxPaths

logger = logging.getLogger(__name__)

# 一条消息最多附几个。挡的不是恶意（归属早进了 WHERE），是「一次拖 50 个」
# 这种把整轮回复拖慢到不可用的操作 —— 每个附件都是一次对象存储读 + 一次灌容器。
_MAX_ATTACHMENTS = 5


async def resolve_refs(
        content: Sequence[ContentBlock], user: User
) -> tuple[list[ContentBlock], list[SandboxArtifact]]:
    """把 content 里的产物引用解析成真实产物行，并回填展示字段。

    Args:
        content: 前端送来的当前轮 block 数组（此刻 ref 块里只有 artifact_id 可信）
        user: 当前用户 —— 归属校验的唯一依据

    Returns:
        (回填后的 content, 引用到的产物行)。前者拿去落库与拼消息，后者拿去灌字节。
        没有引用块时返回 (原样 content, [])，调用方不必先判断有没有附件。

    Raises:
        ValidationException: 附件个数超上限
        NotFound404: 引用了不存在 / 不属于自己的产物
    """
    # 按出现顺序去重：同一个文件拖两次是误操作，不是「要两份」
    ordered_ids: list[UUID] = []
    for block in content:
        if isinstance(block, ArtifactRefBlock) and block.artifact_id not in ordered_ids:
            ordered_ids.append(block.artifact_id)

    if not ordered_ids:
        return list(content), []

    if len(ordered_ids) > _MAX_ATTACHMENTS:
        raise ValidationException(f"一条消息最多附 {_MAX_ATTACHMENTS} 个文件")

    rows = await SandboxArtifact.filter(id__in=ordered_ids, created_by=user)
    found = {row.id: row for row in rows}

    if any(aid not in found for aid in ordered_ids):
        # 不区分「不存在」与「不是你的」—— 两者对外必须是同一句话，
        # 否则这个端点就成了「拿 id 探别人有没有这个产物」的探针
        raise NotFound404("引用的产物不存在")

    # 回填：展示字段一律以库里的为准。客户端传的那份只是它渲染卡片时手上的
    # 副本，可能过时，更不该由它决定「这个块日后被读成哪个文件」。
    # content_type 也在内 —— 前端靠它挑图标，实时回显与刷新回放才是同一个样子
    filled: list[ContentBlock] = []
    seen: set[UUID] = set()
    for block in content:
        if not isinstance(block, ArtifactRefBlock):
            filled.append(block)
            continue
        if block.artifact_id in seen:
            continue  # 重复引用整块丢掉，免得前端渲出两张一模一样的卡片
        seen.add(block.artifact_id)
        row = found[block.artifact_id]
        filled.append(
            ArtifactRefBlock(
                artifact_id=row.id,
                filename=row.filename,
                size=row.size,
                content_type=row.content_type,
            )
        )

    return filled, [found[aid] for aid in ordered_ids]


def _marker(body: str) -> str:
    """包成 <attachments> 标签。

    用 XML 而不是自然语言，与 <artifacts>（决策 24）同源：跟正文长得越不像，
    模型越分得清「这是系统标的，不是我写的」。
    """
    return f"<attachments>{body}</attachments>"


def _unique_name(taken: set[str], filename: str) -> str:
    """同一批里撞名的，从第二个起加 -2 / -3 后缀（浏览器下载同款做法）。

    撞名不是假想：两个对话各自产出过 chart.svg，一起拖进来就撞。
    后写覆盖先写等于悄悄吞掉一个用户明确附上的文件。
    """
    if filename not in taken:
        return filename

    stem, dot, ext = filename.rpartition(".")
    if not dot or not stem:  # 无扩展名，或 .env 这种纯扩展名，整个当主干
        stem, dot, ext = filename, "", ""

    n = 2
    while f"{stem}-{n}{dot}{ext}" in taken:
        n += 1
    return f"{stem}-{n}{dot}{ext}"


async def _upload(
        backend: SandboxBackendProtocol, files: list[tuple[str, bytes]]
) -> list[str | None]:
    """整批灌进工作区，返回与入参等长的错误列表（None = 这条成了）。

    **整体炸了也不往外抛**：附件送不进去是「这一轮读不到这个文件」，
    不是「这轮回复完蛋」—— 模型收到标注后完全可以换个做法接着走。
    """
    try:
        responses = await backend.aupload_files(files)
    except Exception as exc:
        logger.exception("附件灌入工作区整体失败")
        return [str(exc)] * len(files)
    return [r.error for r in responses]


async def inject_attachments(
        backend: SandboxBackendProtocol,
        paths: SandboxPaths,
        artifacts: Sequence[SandboxArtifact],
) -> str:
    """把附件字节灌进本轮工作区，返回给模型看的那行 <attachments> 标注。

    Args:
        backend: 本轮的执行后端 —— 只有它够得着工作区
        paths: 本轮沙箱路径，只用到 workspace（值由 driver 决定，不是常量）
        artifacts: resolve_refs 解出来的产物行，按用户拖的顺序

    Returns:
        <attachments> 标注行；没有附件时返回空串，调用方按空串跳过即可。
    """
    if not artifacts:
        return ""

    taken: set[str] = set()
    reads: list[tuple[str, bytes]] = []  # (工作区里的绝对路径, 字节)
    failed: list[str] = []

    for artifact in artifacts:
        try:
            data = await storage.read(artifact.storage_key)
        except Exception:
            # 库里有行、存储里没字节 —— 少见但可能（存储抖动 / 手工清过桶）。
            # 记下来接着处理下一个，别让一个坏文件连累其余附件
            logger.exception(
                "附件读取失败 artifact_id=%s key=%s", artifact.id, artifact.storage_key
            )
            failed.append(artifact.filename)
            continue

        name = _unique_name(taken, artifact.filename)
        taken.add(name)
        reads.append((f"{paths.workspace}/{name}", data))

    # 一趟送完，不是一个文件一趟：每趟往返约 0.68s（设计稿 §5 实测）
    errors = await _upload(backend, reads) if reads else []

    placed: list[tuple[str, int]] = []
    # strict=True：万一返回条数对不齐就当场炸，而不是安静地把 A 的结果记成 B 的
    for (target, data), error in zip(reads, errors, strict=True):
        if error:
            logger.warning("附件灌入工作区失败 path=%s error=%s", target, error)
            failed.append(target.rsplit("/", 1)[-1])
            continue
        # 报实际写进去的字节数，不报库里那个 —— 两者理论上相等，
        # 但模型该看到的是「现在工作区里那份」有多大
        placed.append((target, len(data)))

    segments: list[str] = []
    if placed:
        listed = "、".join(f"{path} ({human_size(size)})" for path, size in placed)
        segments.append(f"用户附上的文件，已放入工作区：{listed}")
    if failed:
        segments.append(f"另有文件没能放进工作区、这一轮读不到：{'、'.join(failed)}")
    return _marker("。".join(segments) + "。")


def describe_unavailable(artifacts: Sequence[SandboxArtifact]) -> str:
    """没有沙箱可用时的那行标注 —— 文件确实进不来，就别让模型以为它在。

    **不报错、消息照发**（2026-07-30 用户拍板）：「附件只能给沙箱用」只是这一刀
    的现状，不是永久前提。以后做「接收文件」那一刀（PDF / 图片进模型视野），
    同一个 artifact_ref 块自然多一条去处，这里不返工。
    """
    listed = "、".join(f"{a.filename} ({human_size(a.size)})" for a in artifacts)
    return _marker(
        f"用户附上的文件：{listed}。本轮没有能打开文件的参与者，读不到它们的内容。"
    )
