"""LocalDocker driver 的降级路径单测（决策 22b 第三层）—— 不起容器、不发真请求。

这层的铁律：**沙箱出问题时返回失败结果，不抛异常**。抛出去会炸掉一轮已经
进行到一半的回复；返回一句人话，模型看得懂、还能换个做法接着走。
那 7 个文件工具是 deepagents 的 StructuredTool、不走 CoCoTool 基类，
没有任何自动兜底 —— 兜底就得写在这儿，所以它值得被钉住。

httpx 的 MockTransport 顶掉真实连接：sandboxd 不用起，docker 更不用。
"""

from uuid import uuid4

import httpx
import pytest

from app.services.sandbox.docker_sandbox import DockerSandbox, SandboxUnavailable
from app.services.sandbox.layout import container_paths


def _sandbox(handler, *, timeout: int = 120, max_timeout: int = 600) -> DockerSandbox:
    """造一个「会话已就绪」的 DockerSandbox，HTTP 全部走假运输层。

    直接塞 _session_id 是为了跳过建会话那三步 —— 本文件考的是「会话建好之后
    出岔子怎么办」，建会话本身另说。
    """
    box = DockerSandbox(
        paths=container_paths(uuid4()),
        skill_tar=b"",
        env={},
        timeout=timeout,
        max_timeout=max_timeout,
    )
    box._session_id = "sess-1"
    box._http = httpx.Client(
        transport=httpx.MockTransport(handler), base_url="http://sandboxd"
    )
    return box


def _ok(payload: dict) -> httpx.Response:
    return httpx.Response(200, json=payload)


# ---------- 正常路径：透传三个字段 ----------

def test_execute_passes_through_exit_code_and_truncated():
    box = _sandbox(
        lambda _r: _ok({"output": "hello", "exit_code": 3, "truncated": True})
    )

    result = box.execute("echo hello")

    assert (result.output, result.exit_code, result.truncated) == ("hello", 3, True)


# ---------- 超时夹取：越界的值不该让 sandboxd 返 422 ----------

@pytest.mark.parametrize(
    ("asked", "expected"),
    [(None, 120), (30, 30), (99999, 600), (0, 1), (-5, 1)],
)
def test_execute_clamps_timeout_before_sending(asked: int | None, expected: int):
    """sandboxd 那边的 schema 是 gt=0 / le=600，越界直接 422 ——
    而 422 是「客户端发错了」，不该让模型去猜。"""
    seen: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        import json

        seen.append(json.loads(request.content)["timeout"])
        return _ok({"output": "", "exit_code": 0, "truncated": False})

    _sandbox(handler).execute("true", timeout=asked)

    assert seen == [expected]


# ---------- 降级三态 ----------

def test_409_means_container_is_gone_and_says_so():
    """409 = 容器活过 TTL 被反收割清掉。

    **刻意不当场重建**：重建能拿到一个容器，但本轮之前写进 /workspace、/tmp
    的东西全没了，模型会拿着不存在的文件接着往下走。说清楚比假装无事好。
    """
    box = _sandbox(lambda _r: httpx.Response(409, text="session gone"))

    result = box.execute("ls")

    assert result.exit_code == 1
    assert "已失效" in result.output and "已不存在" in result.output


def test_409_clears_session_so_the_next_command_can_reopen():
    """清 _session_id 是为了下一条命令能重新开局，不是为了救这一条。"""
    box = _sandbox(lambda _r: httpx.Response(409))
    box.execute("ls")

    assert box._session_id is None


def test_http_500_is_reported_not_raised():
    box = _sandbox(lambda _r: httpx.Response(500, text="boom"))

    result = box.execute("ls")

    assert result.exit_code == 1 and "500" in result.output


def test_connection_failure_is_reported_not_raised():
    """sandboxd 没起（本地开发常态）—— 返回一句人话，不炸整轮回复。"""

    def handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    result = _sandbox(handler).execute("ls")

    assert result.exit_code == 1 and "沙箱通信失败" in result.output


def test_sandbox_unavailable_during_lazy_start_is_reported_not_raised():
    """懒启动那一刻起容器失败 —— 同样翻成失败结果。"""
    box = _sandbox(lambda _r: _ok({}))
    box._session_id = None  # 强制走 _ensure → _open_session
    box._http = httpx.Client(
        transport=httpx.MockTransport(
            lambda _r: httpx.Response(503, text="no docker")
        ),
        base_url="http://sandboxd",
    )

    result = box.execute("ls")

    assert result.exit_code == 1 and "沙箱不可用" in result.output


# ---------- upload_files：相对路径当场判掉，且不打乱顺序 ----------

def test_relative_paths_are_rejected_without_a_round_trip():
    """tar 解在 / 上，相对路径会落到不知道哪儿去。"""
    sent: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        return httpx.Response(200)

    responses = _sandbox(handler).upload_files([("relative/x.txt", b"x")])

    assert responses[0].error == "invalid_path"
    assert sent == []  # 一趟都没发


def test_upload_responses_keep_input_order():
    """基类要求 response[i] 对 files[i] —— 调用方可能按下标对，别让它错位。"""
    box = _sandbox(lambda _r: httpx.Response(200))

    responses = box.upload_files(
        [("/workspace/a.txt", b"a"), ("bad.txt", b"b"), ("/workspace/c.txt", b"c")]
    )

    assert [r.path for r in responses] == ["/workspace/a.txt", "bad.txt", "/workspace/c.txt"]
    assert [r.error for r in responses] == [None, "invalid_path", None]


def test_close_is_idempotent_and_never_raises():
    """用户掐断对话时这里根本执行不到，真正兜底的是 sandboxd 的反收割 ——
    但被调到时不能再添乱。"""
    box = _sandbox(lambda _r: httpx.Response(500))

    box.close()
    box.close()  # 再来一次也不许炸

    assert box._session_id is None


def test_id_does_not_start_a_container():
    """读一个 id 不该把容器起起来。"""
    box = _sandbox(lambda _r: pytest.fail("不该发任何请求"))
    box._session_id = None

    assert box.id == "docker:pending"


def test_sandbox_unavailable_is_its_own_type():
    """单独成类型，第三层降级才接得准 —— 别的异常不该被这条路吞掉。"""
    assert issubclass(SandboxUnavailable, RuntimeError)
