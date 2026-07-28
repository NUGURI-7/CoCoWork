"""sandboxd 的 docker 操作层 —— 全项目唯一碰 docker SDK 的地方。

它必须活在独立进程里（决策 10）：挂 docker.sock ≈ 交出「在本机起任意容器」的
权力，而 web 是对外开着 API 的那个进程，不该拿这个权力。
"""

import logging
import time
import socket as socket_mod
from functools import lru_cache

import docker
from docker.models.containers import Container

from app.core.config import settings

logger = logging.getLogger(__name__)

# 打在容器上的标记，反收割靠它找漏网的 —— 一次性容器，谁都不该活过一轮回复
LABEL_MARKER = "cocowork.sandbox"

LABEL_CREATED_AT = "cocowork.created_at"

# 四个可写挂载点全是内存盘：容器一停内容自动消失，不占磁盘、无需清理（决策 16）。
# 注意 tmpfs 吃的是**容器自己的内存额度**，所以 SANDBOX_MEMORY_MB 要同时覆盖
# 「脚本吃的内存 + 落在这四个目录里的文件」，不能只按脚本峰值估。
_TMPFS = {
    "/skills": "rw,exec,nosuid,size=64m,mode=1777",
    "/workspace": "rw,exec,nosuid,size=128m,mode=1777",
    "/outputs": "rw,nosuid,size=128m,mode=1777",  # 只放产物，不需要可执行
    "/tmp": "rw,exec,nosuid,size=128m,mode=1777",
}


@lru_cache(maxsize=1)
def get_client() -> docker.DockerClient:
    """连 docker daemon，进程内单例。

    version="auto" 是硬要求：daemon 可能比 SDK 老好几年（实测服务器 23.0.6 /
    API 1.42），不协商会直接报 "client version is too new"。

    **不要加 use_ssh_client=True**：那条路走系统 ssh 命令，能吃到 ~/.ssh/config 的
    连接复用，但**不支持 exec 所需的劫持连接**（docker 要把 HTTP 升级成双向裸流），
    实测 exec_start 永远挂住。默认的 paramiko 路径支持，且同样会读 ~/.ssh/config 的
    hostname / user / identityfile，主机别名照常生效。
    """
    if settings.SANDBOX_DOCKER_HOST:
        return docker.DockerClient(
            base_url=settings.SANDBOX_DOCKER_HOST,
            version="auto",
        )
    return docker.from_env(version="auto")


def ensure_network() -> None:
    """保证专用网络存在（决策 17）。

    网络里只有沙箱容器自己 —— PG / Redis / web 都不在，所以脚本能出公网、
    连不到内部服务。靠拓扑隔离而非 iptables 规则集，Mac / Linux 行为一致。
    """
    client = get_client()
    try:
        client.networks.get(settings.SANDBOX_NETWORK)
    except docker.errors.NotFound:
        client.networks.create(settings.SANDBOX_NETWORK, driver="bridge")
        logger.info("已创建沙箱专用网络 %s", settings.SANDBOX_NETWORK)


def create_container(session_id: str, env: dict[str, str]) -> Container:
    """起一个加固过的一次性容器，返回已启动的句柄。

    env 是解密后的 skill 凭据，注入时机就是此刻（决策 15）—— 起容器时给一次，
    之后每条 docker exec 自动带着，不靠 shell export。
    """
    container = get_client().containers.create(
        image=settings.SANDBOX_IMAGE,
        name=f"cocowork-sbx-{session_id}",
        labels={LABEL_MARKER: "1", LABEL_CREATED_AT: str(int(time.time()))},
        environment=env,
        user="nobody",  # 不以 root 跑
        network=settings.SANDBOX_NETWORK,
        read_only=True,  # 根文件系统只读
        tmpfs=_TMPFS,
        mem_limit=f"{settings.SANDBOX_MEMORY_MB}m",
        # 不写这条，超出内存会去吃 swap，--memory 就形同虚设
        memswap_limit=f"{settings.SANDBOX_MEMORY_MB}m",
        nano_cpus=int(settings.SANDBOX_CPUS * 1_000_000_000),
        pids_limit=settings.SANDBOX_PIDS_LIMIT,  # 防 fork 炸弹
        cap_drop=["ALL"],  # 收掉全部内核特权
        security_opt=["no-new-privileges:true"],  # 容器内提不了权
        working_dir="/tmp",  # 相对路径落草稿区（设计稿 C.1）
    )

    container.start()
    return container


import shlex
from dataclasses import dataclass

# 单条命令的输出上限。deepagents 那边还会再按 token 截一道，这里挡的是更粗暴的
# 情况：一个脚本 print 出几百兆，把 sandboxd 自己的内存吃光。
_MAX_OUTPUT_BYTES = 256 * 1024


@dataclass(frozen=True, slots=True)
class ExecResult:
    output: str  # stdout 与 stderr 合并，顺序就是真实输出顺序
    exit_code: int
    truncated: bool


def exec_command(container: Container, command: str, timeout: int) -> ExecResult:
    """在容器里跑一条命令，返回合并输出 + 退出码。

        超时靠**容器里的 `timeout` 命令**，不靠 SDK —— docker 的 exec API 根本没有超时
        参数，命令挂住就只能干等。coreutils 的 `timeout` 到点发 SIGTERM、再过 5 秒补
        SIGKILL，退出码固定 124，据此翻成人话给模型看。
    """
    api = get_client().api
    wrapped = f"timeout -k 5 {timeout} sh -c {shlex.quote(command)}"

    exec_id = api.exec_create(
        container.id,
        cmd=["sh", "-c", wrapped],
        workdir="/tmp",  # 脚本随手写的相对路径落草稿区（设计稿 C.1）
        user="nobody",
        stdout=True,
        stderr=True,
    )["Id"]

    chunks: list[bytes] = []
    size = 0

    for chunk in api.exec_start(exec_id, stream=True):
        remaining = _MAX_OUTPUT_BYTES - size
        if remaining > 0:
            chunks.append(chunk[:remaining])
        size += len(chunk)
        # 超限后**继续读、只是不再攒**：提前 break 会让容器里的进程卡在写管道上，
        # 于是拿不到退出码。宁可多读一会儿，反正 timeout 卡着总时长。

    exit_code = api.exec_inspect(exec_id)["ExitCode"]
    output = b"".join(chunks).decode("utf-8", errors="replace")

    if exit_code == 124:
        output += f"\n[命令超过 {timeout} 秒未结束，已被终止]"

    return ExecResult(
        output=output,
        exit_code=exit_code,
        truncated=size > _MAX_OUTPUT_BYTES,
    )

# 单次取回上限。容器里的 tmpfs 已经限了 128m，这是第二道独立的闸 ——
# 防「哪天有人把 tmpfs 调大了，却忘了这边」。两道闸不互相依赖才有意义。
_MAX_DOWNLOAD_BYTES = 64 * 1024 * 1024
# 灌完数据后等容器里的 tar 收尾的上限。每次轮询是一趟网络往返，别设太密。
_UPLOAD_WAIT = 30

def upload(container: Container, dest_dir: str, tar_bytes: bytes) -> None:
    """把一个 tar 灌进容器的指定目录，由容器内的 tar 解开。

    **不用 docker 的 put_archive**：那个接口读写的是容器的可写层，
    够不着 tmpfs 挂载（实测 500）。而我们四个可写目录全是 tmpfs —— 内存盘、
    带 size 上限、容器一停即消失，这三条都不想拿去换。

    走 exec 的 stdin 反而更省：deepagents 自带 backend 是 base64 塞进命令行，
    这里直接灌裸字节，不膨胀 33%，也不受 argv 单参数 128KB 的限制。
    """
    api = get_client().api
    exec_id = api.exec_create(
        container.id,
        cmd=["tar", "-x", "-C", dest_dir],
        stdin=True, stdout=True, stderr=True, user="nobody",
    )["Id"]

    sock = api.exec_start(exec_id, socket=True)
    raw = getattr(sock, "_sock", sock)  # paramiko 传输把真 socket 包了一层

    try:
        raw.sendall(tar_bytes)
        # 关掉写端 —— tar 靠「读到 EOF」知道数据到齐了，不关它会一直等
        raw.shutdown(socket_mod.SHUT_WR)
    finally:
        sock.close()

    deadline = time.time() + _UPLOAD_WAIT
    while api.exec_inspect(exec_id)["Running"]:
        if time.time() > deadline:
            raise RuntimeError(f"解包到容器超时：{dest_dir}")
        time.sleep(0.1)

    exit_code = api.exec_inspect(exec_id)["ExitCode"]
    if exit_code != 0:
        raise RuntimeError(f"解包到容器失败：{dest_dir}（tar 退出码 {exit_code}）")


def download(container: Container, path: str) -> bytes:
    """把容器里的一个文件或目录打成 tar 取回来。

    条目名相对于父目录（取 /outputs/msg-1 得到 msg-1/xxx），与 docker 原生
    get_archive 的形状一致 —— 调用方的解包代码不用区分是哪种实现。

    Raises:
        FileNotFoundError: 路径不存在（一轮没产出时是常态，不是错误）
    """
    parent, _, name = path.rstrip("/").rpartition("/")
    api = get_client().api
    exec_id = api.exec_create(
        container.id,
        cmd=["tar", "-c", "-C", parent or "/", name],
        stdout=True,
        stderr=False,  # **必须关**：报错文本会跟 tar 字节混在同一个流里，包就废了
        user="nobody",
    )["Id"]

    chunks: list[bytes] = []
    size = 0
    for chunk in api.exec_start(exec_id, stream=True):
        size += len(chunk)
        if size > _MAX_DOWNLOAD_BYTES:
            raise RuntimeError(
                f"取回内容超过 {_MAX_DOWNLOAD_BYTES // 1024 // 1024}MB 上限：{path}"
            )
        chunks.append(chunk)

    if api.exec_inspect(exec_id)["ExitCode"] != 0:
        raise FileNotFoundError(path)

    return b"".join(chunks)




def destroy(container: Container) -> None:
    """销毁容器。

    清理 = 「容器不存在了」，而不是「把里面删干净」（决策 11）—— 于是
    「清理漏网导致跨用户数据泄露」这类 bug 根本不存在。
    force=True 直接 SIGKILL，不跟那个 `sleep infinity` 客气。
    """
    container.remove(force=True)


def reap_expired(max_age_seconds: int) -> int:
    """清掉活太久的沙箱容器，返回清掉的个数。

    **这不是锦上添花，是唯一的兜底。** 用户掐断对话时，web 那边的销毁调用
    根本执行不到 —— 协程被取消，`finally` 里的 await 立刻再抛 CancelledError；
    web 进程崩了同理。所以「容器一定会死」这件事不能押在 web 身上。

    `max_age_seconds=0` 即「全清」，sandboxd 启动时用：会话句柄只存在于本进程
    内存里，进程重启后所有带标记的容器都成了没人认领的孤儿。
    """
    deadline = time.time() - max_age_seconds
    reaped = 0

    # 按 label 的**键**筛，不管值 —— 这就是当初值随便写 "1" 的原因
    for c in get_client().containers.list(all=True, filters={"label": LABEL_MARKER}):
        try:
            born = float(c.labels.get(LABEL_CREATED_AT, 0))
        except ValueError:
            born = 0  # 标签坏了当远古容器处理，清掉；留着才是风险
        if born > deadline:
            continue

        try:
            c.remove(force=True)
            reaped += 1
            logger.warning("反收割：容器 %s 超过 %ds 未销毁，已强制清理", c.name, max_age_seconds)
        except docker.errors.NotFound:
            pass  # 正常流程刚好抢先删了，不是错

    return reaped









