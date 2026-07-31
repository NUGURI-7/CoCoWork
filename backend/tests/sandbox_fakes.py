"""沙箱单测共用的假件 —— 一个够用的 backend 和一个够用的 storage。

**只实现被测代码真正调到的那几个方法**，不去模仿 SandboxBackendProtocol 的全部
接口：假件越像真的，越容易在真接口变了之后还静静地跑绿灯。少实现一个方法，
被测代码哪天多调了什么，这里会当场 AttributeError —— 那正是我们想要的响声。
"""

from collections.abc import Sequence

from deepagents.backends.protocol import ExecuteResponse, FileUploadResponse


class FakeBackend:
    """记下收到了什么，返回预先安排好的结果。"""

    def __init__(
            self,
            *,
            output: str = "[]",
            exit_code: int = 0,
            upload_errors: Sequence[str | None] | None = None,
            upload_raises: Exception | None = None,
    ) -> None:
        self._output = output
        self._exit_code = exit_code
        self._upload_errors = upload_errors
        self._upload_raises = upload_raises

        self.commands: list[str] = []
        self.uploaded: list[tuple[str, bytes]] = []

    async def aexecute(self, command: str, *, timeout: int | None = None) -> ExecuteResponse:
        self.commands.append(command)
        return ExecuteResponse(
            output=self._output, exit_code=self._exit_code, truncated=False
        )

    async def aupload_files(
            self, files: list[tuple[str, bytes]]
    ) -> list[FileUploadResponse]:
        if self._upload_raises is not None:
            raise self._upload_raises
        self.uploaded.extend(files)
        errors = self._upload_errors or [None] * len(files)
        return [
            FileUploadResponse(path=path, error=error)
            for (path, _), error in zip(files, errors, strict=True)
        ]


class FakeStorage:
    """按 key 发字节；key 落在 broken 里就抛 —— 模拟存储抖动 / 对象被清掉。"""

    def __init__(self, blobs: dict[str, bytes], broken: set[str] | None = None) -> None:
        self._blobs = blobs
        self._broken = broken or set()

    async def read(self, key: str) -> bytes:
        if key in self._broken:
            raise RuntimeError(f"存储读取失败：{key}")
        return self._blobs[key]
