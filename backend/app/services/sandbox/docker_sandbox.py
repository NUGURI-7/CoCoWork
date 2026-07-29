"""LocalDocker driver 的 web 侧客户端 —— 把 backend 调用转成对 sandboxd 的 HTTP。

web 进程永远不碰 docker SDK（决策 10）：这里发出去的是 loopback 上的 HTTP 请求，
docker 那半全在 sandboxd 进程里。

**容器懒启动（决策 22a）**：造这个对象不起容器，第一次真有人调它的方法才起。
挂了 skill 的对话未必真会用沙箱，提前起就是白付启动开销（实测首次阻塞 2.10s，
见设计稿 §5）。

**为什么用同步的 httpx.Client 而不是 AsyncClient**：那 7 个文件工具虽然是 async 的，
但 BaseSandbox 的 async 方法默认实现是 `asyncio.to_thread(同步版本)` —— 我们写的
方法最终跑在 worker 线程里，卡住的是那个线程，不是事件循环。写成 async 反而要
和基类的派生逻辑打架。
"""

import logging
import threading
import io
import tarfile
import time

import httpx
from deepagents.backends.sandbox import BaseSandbox
from deepagents.backends.protocol import ExecuteResponse, FileDownloadResponse, FileUploadResponse

from app.core.config import settings
from app.services.sandbox.layout import SandboxPaths

logger = logging.getLogger(__name__)

# 建会话 / 销毁这类瞬时调用的上限。容器创建实测 0.75s（远程 daemon），给到 60s
# 是为了容忍镜像首次拉取和 daemon 抖动
_CONTROL_TIMEOUT = 60

# 在 sandboxd 的命令超时之外再留一截：HTTP 客户端必须比容器里的 timeout 更有耐心，
# 否则命令还在跑、客户端先放弃，那条命令就成了没人收尸的孤儿
_HTTP_MARGIN = 30


def _pack_tar(members: list[tuple[str, bytes]]) -> bytes:
    """把「绝对路径 → 字节」打成 tar，成员名去掉开头的 `/`（tar 不收绝对路径）。

    **只放文件条目、不放目录条目**：容器里 /skills /workspace /outputs /tmp 都是
    已经挂好的 tmpfs，带上目录条目会让 tar 去改这些挂载点的权限和属主，
    在 --user nobody 下多半直接失败。缺失的中间层不用操心，tar 解包时自己会建。
    """
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tar:
        now = int(time.time())
        for path, content in members:
            info = tarfile.TarInfo(name=path.lstrip("/"))
            info.size = len(content)
            info.mtime = now
            info.mode = 0o644
            tar.addfile(info, io.BytesIO(content))
    return buf.getvalue()


def _unpack_single(tar_bytes: bytes) -> bytes:
    """从 sandboxd 回的 tar 里取出那唯一一个文件的内容。

    sandboxd 原样转发容器里 `tar -c` 的输出，条目名相对于父目录。这个方法只
    服务「取一个文件」，所以拿到第一个普通文件就够了。
    """
    with tarfile.open(fileobj=io.BytesIO(tar_bytes), mode="r") as tar:
        for member in tar:
            if member.isfile():
                fp = tar.extractfile(member)
                if fp is not None:
                    return fp.read()
    raise ValueError("下载回来的归档里没有文件")



def _failed(message: str) -> ExecuteResponse:
    """一条没跑成的命令。exit_code 给 1 —— 基类的 ls/read/grep 都靠非零码判失败。"""
    return ExecuteResponse(output=message, exit_code=1, truncated=False)


class SandboxUnavailable(RuntimeError):
    """sandboxd 连不上 / 起不来容器。

    单独成类型是为了第三层降级（决策 22b）：工具捕获它、返回一句人话，
    而不是让整轮回复炸掉。别的异常不该被这条路吞掉。
    """


class DockerSandbox(BaseSandbox):
    """一次回复借还一个容器（决策 11/12），命令走 sandboxd 的 exec。"""

    def __init__(
            self,
            *,
            paths: SandboxPaths,
            skill_tar: bytes,
            env: dict[str, str],
            timeout: int,
            max_timeout: int,
    ) -> None:
        """
                Args:
                    paths: 容器内路径（container_paths 给的那一份）
                    skill_tar: 本轮所有 skill 打成的 tar，起完容器灌进 /skills（决策 21a）
                    env: 注入容器的环境变量，含解密后的 skill 凭据（决策 15）
                    timeout: 单条命令的默认超时（秒）
                    max_timeout: 单条命令的超时上限，决定 HTTP 客户端要等多久
        """
        self._paths = paths
        self._skill_tar = skill_tar
        self._env = env
        self._timeout = timeout
        self._max_timeout = max_timeout

        self._session_id: str | None = None
        self._lock = threading.Lock()

        self._http = httpx.Client(
            base_url=f"http://{settings.SANDBOXD_HOST}:{settings.SANDBOXD_PORT}",
            headers={"X-Sandbox-Token": settings.SANDBOX_TOKEN},
            timeout=httpx.Timeout(max_timeout + _HTTP_MARGIN, connect=5),
        )

    @property
    def id(self) -> str:
        """给日志用的标识。

        **刻意不触发 `_ensure`** —— 读一个 id 不该把容器起起来。
        deepagents 目前根本不读它，但基类要求实现。
        """
        return f"docker:{self._session_id or 'pending'}"

    def _ensure(self) -> str:
        """拿到可用的会话 id；没有就现建一个（懒启动的全部实现）。

        **锁住整段而不是只锁赋值**：并发进来的线程应该一起等这一个容器，
        而不是各建各的。持锁期间的那 1~2 秒 I/O 是有意付的 —— 不锁的话
        两个线程会同时看到 None、各发一次建会话请求，多出来的那个容器
        没人认领，得等 15 分钟 TTL 才被反收割清掉（notes §34 那条缝）。
        """
        with self._lock:
            if self._session_id is None:
                self._session_id = self._open_session()
            return self._session_id

    def _open_session(self) -> str:
        """起容器 → 灌 skill → 建交付区。三步做完才算「会话可用」。

        这三步刻意留在 web 侧、没有并进 sandboxd 的建会话请求：sandboxd 是
        通用的容器管理，不该知道 skill 和交付区是什么。合并也省不到往返 ——
        docker 那几趟该走还是走。
        """
        try:
            resp = self._http.post("/sessions", json={"env": self._env}, timeout=_CONTROL_TIMEOUT)
            resp.raise_for_status()
            session_id = resp.json()["session_id"]
        except httpx.HTTPError as exc:
            # 这一段失败时容器还没起来，没有东西要收拾
            raise SandboxUnavailable(f"沙箱不可用：{exc}") from exc

        # 过了这条线，容器已经在跑了 —— 后面任何一步失败都必须把它销毁掉，
        # 否则它谁也不认识，白占 512MB 直到 15 分钟 TTL 被反收割清掉
        try:
            if self._skill_tar:
                self._http.post(
                    f"/sessions/{session_id}/upload",
                    params={"dest": self._paths.skills},
                    content=self._skill_tar,
                    headers={"Content-Type": "application/x-tar"},
                ).raise_for_status()

            # 交付区：本轮专属的空目录，产物识别的全部前提（C.1）
            self._http.post(
                f"/sessions/{session_id}/exec",
                json={"command": f"mkdir -p {self._paths.outputs}", "timeout": 30},
            ).raise_for_status()
        except httpx.HTTPError as exc:
            self._delete_session(session_id)
            raise SandboxUnavailable(f"沙箱初始化失败：{exc}") from exc

        logger.info("沙箱会话已建立 session=%s outputs=%s", session_id, self._paths.outputs)
        return session_id

    def _delete_session(self, session_id: str) -> None:
        """请 sandboxd 销毁容器。**吞掉所有异常** —— 销毁本身失败不该盖过真正的
        错误原因，而且它从来不是唯一保障：真正兜底的是 sandboxd 的反收割。
        """
        try:
            self._http.delete(f"/sessions/{session_id}", timeout=_CONTROL_TIMEOUT)
        except Exception:
            logger.warning("销毁沙箱会话失败 session=%s，等反收割兜底", session_id, exc_info=True)

    def close(self) -> None:
        """销毁容器并关掉连接。**绝不抛异常，重复调也没事。**

        它不是唯一保障：用户掐断对话时这里根本执行不到（协程被取消），
        真正兜底的是 sandboxd 那边的反收割。
        """
        if self._session_id is not None:
            self._delete_session(self._session_id)
        self._session_id = None
        self._http.close()

    def execute(self, command: str, *, timeout: int | None = None) -> ExecuteResponse:
        """在容器里跑一条命令。

        **沙箱出问题时返回失败结果，而不是抛异常**（决策 22b 第三层降级）：
        抛出去会炸掉整轮已经进行到一半的回复；返回一句人话，模型看得懂，
        还能换个做法接着往下走。
        """
        # 夹一下再发：sandboxd 那边的 schema 是 gt=0 / le=600，越界直接 422，
        # 而 422 是「客户端发错了」，不该让模型去猜
        limit = self._timeout if timeout is None else max(1, min(timeout, self._max_timeout))

        try:
            session_id = self._ensure()
            resp = self._http.post(
                f"/sessions/{session_id}/exec",
                json={"command": command, "timeout": limit},
            )
            resp.raise_for_status()
        except SandboxUnavailable as exc:
            return _failed(str(exc))
        except httpx.HTTPStatusError as exc:
            return self._explain_status(exc)
        except httpx.HTTPError as exc:
            return _failed(f"沙箱通信失败：{exc}")

        data = resp.json()
        return ExecuteResponse(
            output=data["output"],
            exit_code=data["exit_code"],
            truncated=data["truncated"],
        )

    def _explain_status(self, exc: httpx.HTTPStatusError) -> ExecuteResponse:
        """把 sandboxd 的错误码翻成给模型看的一句话。

        **409 要单独说** —— 它的意思是「容器已经不在了」（活过 TTL 被反收割清掉）。
        这里刻意**不当场重建**：重建能拿到一个容器，但本轮之前写进 /workspace、
        /tmp 的东西全没了，模型会拿着不存在的文件接着往下走。说清楚比假装无事好。
        清空 _session_id 是为了下一条命令能重新开局，而不是为了救这一条。
        """
        if exc.response.status_code == 409:
            self._session_id = None
            return _failed("沙箱会话已失效（容器存活超时被回收），本轮之前写下的文件已不存在。")
        return _failed(f"沙箱返回错误 {exc.response.status_code}：{exc.response.text}")

    def upload_files(self, files: list[tuple[str, bytes]]) -> list[FileUploadResponse]:
        """把若干文件放进容器。

        **一次打成一个 tar、一趟往返送完**，不是一个文件一趟：远程 daemon 下每趟
        约 0.68s（实测，设计稿 §5），按文件拆开会成倍放大。

        代价照实记：这一趟一旦失败，整批一起标失败，做不到「这个成了那个没成」。
        基类要求支持部分成功，而实际调用方每次只送 1~2 个文件（write 送一个、
        edit 送新旧两份），拆成 N 趟换来的粒度不值那几秒。
        """
        failures: dict[str, str] = {}
        members: list[tuple[str, bytes]] = []

        for path, content in files:
            if path.startswith("/"):
                members.append((path, content))
            else:
                # tar 解在 / 上，相对路径会落到不知道哪儿去，当场判掉
                failures[path] = "invalid_path"

        if members:
            try:
                session_id = self._ensure()
                self._http.post(
                    f"/sessions/{session_id}/upload",
                    params={"dest": "/"},
                    content=_pack_tar(members),
                    headers={"Content-Type": "application/x-tar"},
                ).raise_for_status()
            except (SandboxUnavailable, httpx.HTTPError) as exc:
                for path, _ in members:
                    failures[path] = f"上传失败：{exc}"

        # 按入参顺序原样返回：调用方可能按下标对，别让它错位
        return [FileUploadResponse(path=path, error=failures.get(path)) for path, _ in files]

    def download_files(self, paths: list[str]) -> list[FileDownloadResponse]:
        """从容器里取文件。**一个文件一趟** —— sandboxd 的下载接口一次只收一个路径。

        逐个 try：一个取不到不该连累别的（基类明确要求支持部分成功）。这里能
        逐个来，是因为下载本来就是一路一趟，拆开不多付往返。
        """

        results: list[FileDownloadResponse] = []

        for path in paths:
            try:
                session_id = self._ensure()
                resp = self._http.post(f"/sessions/{session_id}/download", json={"path": path})
                resp.raise_for_status()
                content = _unpack_single(resp.content)
            except httpx.HTTPStatusError as exc:
                # 404 翻成基类认得的那个字面量，模型看到的是「文件不存在」而不是一串状态码
                error = "file_not_found" if exc.response.status_code == 404 else f"下载失败：{exc}"
                results.append(FileDownloadResponse(path=path, error=error))
            except (SandboxUnavailable, httpx.HTTPError, ValueError, tarfile.TarError) as exc:
                results.append(FileDownloadResponse(path=path, error=f"下载失败：{exc}"))
            else:
                results.append(FileDownloadResponse(path=path, content=content))

        return results
