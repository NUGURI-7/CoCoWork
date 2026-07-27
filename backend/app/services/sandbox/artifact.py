"""沙箱产物的回收 —— 把交付区里的文件收进对象存储、在表里记一笔。

「哪些文件是产物」这里不需要判断：交付区是每轮新建的空目录，`ls` 一下就是
全部答案（设计稿 C.1 / C.2）。本模块只做三件事：读出来、存起来、记一笔。

失败策略：**整轮回复不因产物回收而失败**。单个文件出问题就跳过并记日志，
其余照收 —— 产物是回复的附赠品，不是回复本身，为它炸掉一次已经完成的对话
是本末倒置。但只要有任何一个失败，就不删交付区目录，留着可人工排查。
"""

import logging
import mimetypes
import shutil
from pathlib import Path
from uuid import UUID

from app.core.config import settings
from app.core.storage import storage
from app.models import User
from app.models.sandbox import SandboxArtifact
from app.services.sandbox.layout import SandboxPaths

logger = logging.getLogger(__name__)

_DEFAULT_CONTENT_TYPE = "application/octet-stream"


async def collect_artifacts(
        paths: SandboxPaths,
        *,
        user: User,
        scope_id: UUID,
        message_id: UUID,
        conversation_id: UUID | None = None,
) -> list[SandboxArtifact]:
    """回收本轮交付区里的产物；没有产物就返回空列表。

    Args:
        paths: 本轮的沙箱路径，只用到 `outputs`
        user: 产物归属人，下载鉴权的依据
        scope_id: 工作区归属键，只用于拼 storage_key（Playground=user.id / workspace=workspace.id）
        message_id: 本轮消息 ID，既是交付区目录名也是产物的归组键
        conversation_id: workspace 对话才有；Playground 传 None

    Returns:
        已成功入库的产物列表，供 SSE 发给前端
    """
    outputs = Path(paths.outputs)

    if not outputs.is_dir():
        return []

    collected: list[SandboxArtifact] = []
    failed = False

    for entry in sorted(outputs.iterdir()):
        if not entry.is_file() or entry.is_symlink():
            # 子目录不收（交付区是扁平的交付口）；符号链接更不能收 ——
            # 它可能指向沙箱外的任意文件，收了等于把宿主机文件当产物送出去
            logger.info("交付区跳过非普通文件 message_id=%s name=%s", message_id, entry.name)
            continue

        size = entry.stat().st_size
        if size > settings.SANDBOX_ARTIFACT_MAX_SIZE:
            mb = settings.SANDBOX_ARTIFACT_MAX_SIZE // (1024 * 1024)
            logger.warning(
                "产物超出 %dMB 上限，跳过 message_id=%s name=%s size=%d",
                mb, message_id, entry.name, size,
            )
            failed = True
            continue

        content_type = mimetypes.guess_type(entry.name)[0] or _DEFAULT_CONTENT_TYPE
        storage_key = f"sandbox/{scope_id}/{message_id}/{entry.name}"

        try:
            with entry.open("rb") as fp:
                await storage.save(storage_key, fp, content_type=content_type)

            collected.append(
                await SandboxArtifact.create(
                    created_by=user,
                    conversation_id=conversation_id,
                    message_id=message_id,
                    filename=entry.name,
                    size=size,
                    content_type=content_type,
                    storage_key=storage_key,
                )
            )
        except Exception:
            # 存储抖动 / 唯一约束撞车 —— 记下来跳过，不连累其余产物，更不连累这轮回复
            logger.exception(
                "产物回收失败 message_id=%s name=%s key=%s",
                message_id, entry.name, storage_key,
            )
            failed = True
    if not failed:
        # 全部收走了，交付区没有留存价值 —— 删掉，免得目录逐轮堆积。
        # 有失败时刻意保留：那些文件还没有任何下载入口，删了就真没了。
        shutil.rmtree(outputs, ignore_errors=True)

    return collected






