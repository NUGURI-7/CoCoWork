"""sandboxd 的 HTTP 面 —— web 唯一能碰到 docker 的方式。

**只监听 127.0.0.1，且每个请求要带共享密钥**：这个进程挂着 docker.sock，
等于握着「在本机起任意容器」的权力（§3）。它一旦对外，整台机器就交出去了。
"""

import logging
import secrets
from typing import NoReturn

import docker
from docker.models.containers import Container
from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from starlette.concurrency import run_in_threadpool

from app.core.config import settings
from app.sandbox import container as docker_ops
from app.sandbox.schemas import (
    DownloadRequest,
    ExecRequest,
    ExecResponse,
    OpenSessionRequest,
    OpenSessionResponse,
)
from app.sandbox.session import registry

logger = logging.getLogger(__name__)


def verify_token(x_sandbox_token: str = Header(default="")) -> None:
    """共享密钥校验。

    用 secrets.compare_digest 而不是 == ：字符串相等比较会在第一个不同的字符处
    提前返回，逐字节试探就能把密钥猜出来（时序攻击）。这条链路只走本机，
    但改对它是一行的事。
    """
    if not secrets.compare_digest(x_sandbox_token, settings.SANDBOX_TOKEN):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "sandboxd 令牌不正确")


router = APIRouter(dependencies=[Depends(verify_token)])


def _get_container(session_id: str) -> Container:
    """按 id 取容器句柄；登记簿里没有就是 404。"""
    try:
        return registry.get(session_id)
    except KeyError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "会话不存在")


def _drop_dead_session(session_id: str) -> NoReturn:
    """容器已经不在了（多半被反收割清了）：清掉登记簿里的死记录，回 409。

    与 404 分开是有意的 —— 404 是正常的生老病死，409 说明有会话活过了 TTL，
    是该翻日志追一下的异常信号。两个混成一个码，那个信号就永远看不见了。
    """
    registry.close(session_id)
    logger.warning("会话 %s 的容器已消失，多半被反收割清理", session_id)
    raise HTTPException(status.HTTP_409_CONFLICT, "会话已失效，请重新建立")


@router.post("/sessions", response_model=OpenSessionResponse)
def open_session(req: OpenSessionRequest) -> OpenSessionResponse:
    """起一个加固容器。约 1-3 秒，由 web 侧在第一次用到工具时才调（决策 22a）。"""
    return OpenSessionResponse(session_id=registry.open(req.env))


@router.post("/sessions/{session_id}/exec", response_model=ExecResponse)
def exec_in_session(session_id: str, req: ExecRequest) -> ExecResponse:
    container = _get_container(session_id)
    try:
        result = docker_ops.exec_command(container, req.command, req.timeout)
    except docker.errors.NotFound:
        _drop_dead_session(session_id)

    return ExecResponse(
        output=result.output,
        exit_code=result.exit_code,
        truncated=result.truncated,
    )


@router.post("/sessions/{session_id}/upload", status_code=status.HTTP_204_NO_CONTENT)
async def upload(session_id: str, dest: str, request: Request) -> None:
    """把请求体里的 tar 解进容器的 dest 目录。

    只有这个端点是 async：读请求体必须 await。于是阻塞的那半（docker 调用）
    得手动挪进线程池，否则它会卡住整个事件循环 —— 别的端点是 def，
    FastAPI 自动这么干，这里是自己干。
    """
    tar_bytes = await request.body()
    container = _get_container(session_id)
    try:
        await run_in_threadpool(docker_ops.upload, container, dest, tar_bytes)
    except docker.errors.NotFound:
        _drop_dead_session(session_id)


@router.post("/sessions/{session_id}/download")
def download(session_id: str, req: DownloadRequest) -> Response:
    """取容器里的文件或目录，原样吐 tar 字节。"""
    container = _get_container(session_id)
    try:
        tar_bytes = docker_ops.download(container, req.path)
    except FileNotFoundError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"路径不存在：{req.path}")
    except docker.errors.NotFound:
        _drop_dead_session(session_id)
    return Response(content=tar_bytes, media_type="application/x-tar")


@router.delete("/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def close_session(session_id: str) -> None:
    """销毁容器。会话已经不存在也算成功 —— 销毁是幂等的，重复调不该报错。"""
    registry.close(session_id)