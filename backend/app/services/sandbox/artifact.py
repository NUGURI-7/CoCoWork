"""沙箱产物的回收 —— 把交付区里的文件收进对象存储、在表里记一笔。

「哪些文件是产物」这里不需要判断：交付区是每轮新建的空目录，`ls` 一下就是
全部答案（设计稿 C.1 / C.2）。本模块只做三件事：读出来、存起来、记一笔。

失败策略：**整轮回复不因产物回收而失败**。单个文件出问题就跳过并记日志，
其余照收 —— 产物是回复的附赠品，不是回复本身，为它炸掉一次已经完成的对话
是本末倒置。但只要有任何一个失败，就不删交付区目录，留着可人工排查。
"""

import base64
import io
import json
import logging
import mimetypes
import shlex
from uuid import UUID

from deepagents.backends.protocol import SandboxBackendProtocol

from app.core.config import settings
from app.core.storage import storage
from app.models import User
from app.models.sandbox import SandboxArtifact
from app.services.sandbox.layout import SandboxPaths

logger = logging.getLogger(__name__)

_DEFAULT_CONTENT_TYPE = "application/octet-stream"

# 列交付区用的命令模板。**用 python3 而不是 `find -printf`**：后者是 GNU 专有参数，
# 容器（Linux/GNU）有、开发机（macOS/BSD）没有，而这条命令两个 driver 都要跑。
# 路径走 base64 传进去，免得文件名里的引号空格把 shell 引用规则搅烂 ——
# 这个套路是照抄 deepagents 自己的 BaseSandbox.ls。
_LIST_DELIVERY = """python3 -c "
import base64, json, os

path = base64.b64decode('{path_b64}').decode('utf-8')
found = []
try:
    with os.scandir(path) as it:
        for entry in it:
            # follow_symlinks=False：符号链接不算普通文件，直接落选。
            # 它可能指向沙箱外的任意文件，收了等于把宿主机文件当产物送出去
            if entry.is_file(follow_symlinks=False):
                found.append([entry.name, entry.stat().st_size])
except FileNotFoundError:
    pass
print(json.dumps(found))
" 2>/dev/null"""


async def _list_delivery(backend: SandboxBackendProtocol, outputs: str) -> list[tuple[str, int]]:
    """列出交付区里的普通文件，返回 [(文件名, 字节数)]。

        **先拿大小、再决定下不下载**：一个超限的大文件如果先下回来再判断，
        那几十兆已经进了 web 进程的内存 —— 判断本身就失去了意义。

        交付区不存在（这一轮没挂 skill / 没起容器）不是错误，返回空。
        """
    path_b64 = base64.b64encode(outputs.encode("utf-8")).decode("ascii")
    result = await backend.aexecute(_LIST_DELIVERY.format(path_b64=path_b64))

    if result.exit_code != 0:
        logger.warning("列交付区失败 path=%s exit=%s", outputs, result.exit_code)
        return []

    try:
        return [(name, size) for name, size in json.loads(result.output.strip() or "[]")]
    except (ValueError, TypeError):
        logger.warning("交付区清单解析失败 path=%s output=%r", outputs, result.output[:200])
        return []


async def collect_artifacts(
        backend: SandboxBackendProtocol,
        paths: SandboxPaths,
        *,
        user: User,
        scope_id: UUID,
        message_id: UUID,
        conversation_id: UUID | None = None,
) -> list[SandboxArtifact]:
    """回收本轮交付区里的产物；没有产物就返回空列表。

    Args:
        backend: 本轮的执行后端 —— 交付区只有它够得着
        paths: 本轮的沙箱路径，只用到 `outputs`
        user: 产物归属人，下载鉴权的依据
        scope_id: 工作区归属键，只用于拼 storage_key（Playground=user.id / workspace=workspace.id）
        message_id: 本轮消息 ID，既是交付区目录名也是产物的归组键
        conversation_id: workspace 对话才有；Playground 传 None

    Returns:
        已成功入库的产物列表，供 SSE 发给前端
    """
    entries = await _list_delivery(backend, paths.outputs)
    if not entries:
        return []

    failed = False
    wanted: list[str] = []

    for name, size in entries:
        if size > settings.SANDBOX_ARTIFACT_MAX_SIZE:
            mb = settings.SANDBOX_ARTIFACT_MAX_SIZE // (1024 * 1024)
            logger.warning(
                "产物超出 %dMB 上限，跳过 message_id=%s name=%s size=%d",
                mb, message_id, name, size,
            )
            failed = True
            continue
        wanted.append(name)

    if not wanted:
        return []

    # 一次把该要的都要回来。取回的顺序与请求顺序一一对应，strict=True 让
    # 「万一对不齐」当场炸掉，而不是安静地把 A 的字节存成 B 的产物
    responses = await backend.adownload_files([f"{paths.outputs}/{name}" for name in wanted])

    collected: list[SandboxArtifact] = []

    for name, response in zip(wanted, responses, strict=True):
        if response.error or response.content is None:
            logger.warning(
                "产物取回失败 message_id=%s name=%s error=%s", message_id, name, response.error
            )
            failed = True
            continue

        content_type = mimetypes.guess_type(name)[0] or _DEFAULT_CONTENT_TYPE
        storage_key = f"sandbox/{scope_id}/{message_id}/{name}"

        try:
            await storage.save(
                storage_key, io.BytesIO(response.content), content_type=content_type
            )
            collected.append(
                await SandboxArtifact.create(
                    created_by=user,
                    conversation_id=conversation_id,
                    message_id=message_id,
                    filename=name,
                    # 记实际收到的字节数，不用列清单时那个 —— 两者理论上相等，
                    # 但入库的该是「真正存进去的那份」有多大
                    size=len(response.content),
                    content_type=content_type,
                    storage_key=storage_key,
                )
            )
        except Exception:
            # 存储抖动 / 唯一约束撞车 —— 记下来跳过，不连累其余产物，更不连累这轮回复
            logger.exception(
                "产物回收失败 message_id=%s name=%s key=%s", message_id, name, storage_key
            )
            failed = True
    if not failed:
        # 全收走了，交付区没有留存价值。有失败时刻意保留：那些文件还没有任何
        # 下载入口，删了就真没了。
        # docker driver 下容器马上就销毁，删不删都一样；但 local driver 的目录
        # 会逐轮堆在磁盘上，所以这一步不能省。
        await backend.aexecute(f"rm -rf {shlex.quote(paths.outputs)}")

    return collected
