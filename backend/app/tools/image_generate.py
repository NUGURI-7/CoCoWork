"""生成配图的工具 —— 调万相生成一张图，下载进本轮工作区，只把路径交给成员。

**per-run bound 实例**，形态同 ArtifactFetchTool：构造时绑本轮的 backend，装配阶段
实例化，不进 registry（离开沙箱它没地方放图）。密钥只在后端，成员拿到的只是文件路径；
图片由后端下载后放进沙箱，沙箱本身不访问外网。
"""

import re
from typing import Any, Literal

import httpx
from deepagents.backends.protocol import SandboxBackendProtocol
from pydantic import BaseModel, ConfigDict, Field

from app.core.config import settings
from app.tools.base import CoCoTool

_ENDPOINT = "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation"

# 万相按总像素（768*768 ~ 2048*2048）和宽高比约束尺寸，这里只开放文档页常用的几种比例
_SIZES = {
    "16:9": "1280*720",
    "4:3": "1152*864",
    "1:1": "1024*1024",
    "3:4": "864*1152",
    "9:16": "720*1280",
}
_UNSAFE_NAME = re.compile(r"[^\w\-]+")


class ImageGenerateInput(BaseModel):
    prompt: str = Field(
        description="画面描述：主体、场景、风格、色调、构图。图里不要出现文字，页面上的文字由版式另外排",
    )
    aspect: Literal["16:9", "4:3", "1:1", "3:4", "9:16"] = Field(
        default="16:9", description="宽高比，按图片在页面上占的位置选",
    )
    filename: str = Field(description="文件名，不带扩展名，如 cover、scene-factory")


class ImageGenerateTool(CoCoTool):
    """按描述生成一张 PNG 配图，存进本轮工作区。"""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str = "generate_image"
    display_name: str = "生成配图"
    description: str = (
        "按画面描述生成一张配图（PNG），保存到工作区并返回文件路径，用于封面、章节页和插图。"
        "一次生成一张、按张计费，只给确实需要配图的位置调用。"
    )
    args_schema: type[BaseModel] = ImageGenerateInput

    timeout_seconds: float = 180.0  # 生图本身要几十秒，再加下载
    max_output_chars: int = 500

    # ---- per-run bound fields（构造时必传，绝不接受模型输入）----
    backend: SandboxBackendProtocol
    workspace_dir: str

    async def _execute(self, prompt: str, filename: str, aspect: str = "16:9") -> str:
        api_key = settings.DASHSCOPE_API_KEY.get_secret_value().strip()
        if not api_key:
            return "生图服务未配置，这次不用配图，直接用版式和色块完成页面。"

        body = {
            "model": settings.IMAGE_GEN_MODEL,
            "input": {"messages": [{"role": "user", "content": [{"text": prompt}]}]},
            "parameters": {"size": _SIZES[aspect], "n": 1, "watermark": False},
        }
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            resp = await client.post(
                _ENDPOINT, json=body, headers={"Authorization": f"Bearer {api_key}"},
            )
            if resp.status_code != 200:
                return f"生成失败：{_error_message(resp)}"
            url = _image_url(resp.json())
            if url is None:
                return "生成失败：服务没有返回图片，换个描述再试一次。"
            # 结果链接 24 小时后失效，当场下载
            image = await client.get(url)
            image.raise_for_status()

        target = f"{self.workspace_dir}/{safe_filename(filename)}.png"
        responses = await self.backend.aupload_files([(target, image.content)])
        error = responses[0].error if responses else "上传没有返回结果"
        if error:
            return f"图片已生成，但存进工作区失败：{error}"
        return f"已生成 {target}（{_SIZES[aspect].replace('*', '×')}）"


def safe_filename(filename: str) -> str:
    """只留字母、数字、汉字、下划线和连字符，防止文件名里带路径跳出工作区。"""
    return _UNSAFE_NAME.sub("-", filename).strip("-") or "image"


def _image_url(data: dict[str, Any]) -> str | None:
    """取 output.choices[0].message.content 里第一张图的链接。"""
    choices = (data.get("output") or {}).get("choices") or []
    if not choices:
        return None
    for item in choices[0].get("message", {}).get("content", []):
        if item.get("type") == "image" and item.get("image"):
            return item["image"]
    return None


def _error_message(resp: httpx.Response) -> str:
    """把服务端的错误码和说明转成一句话（如内容审核不通过），交给模型决定换描述还是放弃。"""
    try:
        data = resp.json()
        return f"{data.get('code', resp.status_code)}，{data.get('message', '')}".rstrip("，")
    except ValueError:
        return f"HTTP {resp.status_code}"
