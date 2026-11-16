"""生图 / 看图两个绑沙箱工具：调用格式、出错时的一句话、装配开关。不真调千问接口。"""

import json
from unittest.mock import MagicMock

import httpx
import pytest
from deepagents.backends.protocol import FileDownloadResponse, SandboxBackendProtocol
from pydantic import SecretStr

from app.core.config import settings
from app.schemas.agent import AgentConfig
from app.services.sandbox.layout import container_paths
from app.services.skill.mount import SkillMount
from app.tools import image_generate, page_review
from app.tools.image_generate import ImageGenerateTool, safe_filename
from app.tools.page_review import PageReviewTool
from app.tools.registry import resolve_tools
from tests.sandbox_fakes import FakeBackend

IMAGE_URL = "https://dashscope-result.example.com/x.png"


class FakeFilesBackend(FakeBackend):
    """在 FakeBackend 上补一个按路径发字节的下载。"""

    def __init__(self, files: dict[str, bytes]) -> None:
        super().__init__()
        self._files = files

    async def adownload_files(self, paths: list[str]) -> list[FileDownloadResponse]:
        return [
            FileDownloadResponse(path=p, content=self._files[p], error=None)
            if p in self._files else FileDownloadResponse(path=p, content=None, error="file_not_found")
            for p in paths
        ]


def _tool(cls, **fields):
    """假 backend 不是 SandboxBackendProtocol 的实例，跳过字段校验直接造工具。"""
    return cls.model_construct(**fields)


@pytest.fixture
def api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "DASHSCOPE_API_KEY", SecretStr("test-key"))


def _mock_http(monkeypatch: pytest.MonkeyPatch, module, handler) -> list[httpx.Request]:
    """把模块里的 httpx.AsyncClient 换成走 MockTransport 的版本，记下发出的请求。"""
    seen: list[httpx.Request] = []
    real = httpx.AsyncClient

    def record(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return handler(request)

    monkeypatch.setattr(
        module.httpx, "AsyncClient",
        lambda **kw: real(transport=httpx.MockTransport(record), **kw),
    )
    return seen


# ---------- 生图 ----------

async def test_generate_without_key_does_not_call_or_upload(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "DASHSCOPE_API_KEY", SecretStr(""))
    backend = FakeBackend()
    tool = _tool(ImageGenerateTool, backend=backend, workspace_dir="/workspace")

    result = await tool._execute(prompt="工厂", filename="cover")

    assert "未配置" in result
    assert backend.uploaded == []


async def test_generate_downloads_into_workspace(monkeypatch: pytest.MonkeyPatch, api_key):
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "dashscope.aliyuncs.com":
            return httpx.Response(200, json={"output": {"choices": [{"message": {
                "content": [{"type": "image", "image": IMAGE_URL}],
            }}]}})
        return httpx.Response(200, content=b"PNGDATA")

    seen = _mock_http(monkeypatch, image_generate, handler)
    backend = FakeBackend()
    tool = _tool(ImageGenerateTool, backend=backend, workspace_dir="/workspace")

    result = await tool._execute(prompt="现代工厂车间", filename="cover", aspect="1:1")

    body = json.loads(seen[0].content)
    assert seen[0].headers["Authorization"] == "Bearer test-key"
    assert body["model"] == settings.IMAGE_GEN_MODEL
    assert body["parameters"]["size"] == "1024*1024"
    assert str(seen[1].url) == IMAGE_URL
    assert backend.uploaded == [("/workspace/cover.png", b"PNGDATA")]
    assert result.startswith("已生成 /workspace/cover.png")
    assert "test-key" not in result


async def test_generate_reports_service_error(monkeypatch: pytest.MonkeyPatch, api_key):
    _mock_http(monkeypatch, image_generate, lambda r: httpx.Response(
        400, json={"code": "DataInspectionFailed", "message": "内容审核未通过"},
    ))
    backend = FakeBackend()
    tool = _tool(ImageGenerateTool, backend=backend, workspace_dir="/workspace")

    result = await tool._execute(prompt="x", filename="cover")

    assert result == "生成失败：DataInspectionFailed，内容审核未通过"
    assert backend.uploaded == []


@pytest.mark.parametrize(("raw", "expected"), [
    ("cover", "cover"),
    ("../../etc/passwd", "etc-passwd"),
    ("场景 工厂", "场景-工厂"),
    ("///", "image"),
])
def test_safe_filename_cannot_escape_workspace(raw: str, expected: str):
    assert safe_filename(raw) == expected


# ---------- 看图 ----------

async def test_review_rejects_non_image_paths(api_key):
    tool = _tool(PageReviewTool, backend=FakeFilesBackend({}))

    result = await tool._execute(image_paths=["/workspace/deck.pptx"])

    assert "不是 PNG / JPG" in result


async def test_review_reports_missing_files(api_key):
    tool = _tool(PageReviewTool, backend=FakeFilesBackend({}))

    result = await tool._execute(image_paths=["/workspace/page-1.png"])

    assert "读不到这些图片" in result and "/workspace/page-1.png" in result


async def test_review_sends_every_page_and_returns_findings(monkeypatch: pytest.MonkeyPatch, api_key):
    seen = _mock_http(monkeypatch, page_review, lambda r: httpx.Response(200, json={
        "choices": [{"message": {"content": "第 1 页：无明显问题\n第 2 页：标题超出右边界"}}],
    }))
    backend = FakeFilesBackend({"/workspace/p1.png": b"A", "/workspace/p2.jpg": b"B"})
    tool = _tool(PageReviewTool, backend=backend)

    result = await tool._execute(image_paths=["/workspace/p1.png", "/workspace/p2.jpg"], focus="第 2 页刚改过")

    body = json.loads(seen[0].content)
    images = [c["image_url"]["url"] for c in body["messages"][1]["content"] if c["type"] == "image_url"]
    assert body["model"] == settings.VISION_MODEL
    assert images == ["data:image/png;base64,QQ==", "data:image/jpeg;base64,Qg=="]
    assert "第 2 页刚改过" in body["messages"][1]["content"][0]["text"]
    assert result == "第 1 页：无明显问题\n第 2 页：标题超出右边界"


async def test_review_failure_says_it_can_be_skipped(monkeypatch: pytest.MonkeyPatch, api_key):
    _mock_http(monkeypatch, page_review, lambda r: httpx.Response(500, text="boom"))
    tool = _tool(PageReviewTool, backend=FakeFilesBackend({"/workspace/p1.png": b"A"}))

    result = await tool._execute(image_paths=["/workspace/p1.png"])

    assert "可以跳过" in result


# ---------- 装配开关 ----------

def _mount() -> SkillMount:
    return SkillMount(
        middleware=None,  # type: ignore[arg-type]  sandbox_tools 用不到
        paths=container_paths("00000000-0000-0000-0000-000000000000"),
        backend=MagicMock(spec=SandboxBackendProtocol),
        artifact_tools=[],
        uploaded={},
    )


def test_sandbox_tools_follow_builtin_tools_switches():
    mount = _mount()

    both = mount.sandbox_tools(AgentConfig(builtin_tools=["generate_image", "review_pages"]))
    image_only = mount.sandbox_tools(AgentConfig(builtin_tools=["generate_image"]))
    none = mount.sandbox_tools(AgentConfig(builtin_tools=["calculator"]))

    assert [t.name for t in both] == ["generate_image", "review_pages"]
    assert both[0].workspace_dir == mount.paths.workspace
    assert [t.name for t in image_only] == ["generate_image"]
    assert none == []


def test_registry_skips_sandbox_bound_names_without_warning(caplog: pytest.LogCaptureFixture):
    with caplog.at_level("WARNING"):
        tools = resolve_tools(["generate_image", "review_pages"])

    assert tools == []
    assert "未知工具" not in caplog.text
