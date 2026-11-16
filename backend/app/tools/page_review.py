"""检查页面效果的工具 —— 把渲染好的页面图片交给视觉模型，返回逐页的版式问题清单。

成员自己的模型不用换：看图由后端调视觉模型完成，成员只读文字结论。
视觉模型会漏报（实测漏过标题溢出），结论是辅助检查，不替代说明书里的文件校验。
per-run bound 实例，形态同 ArtifactFetchTool。
"""

import base64
from pathlib import PurePosixPath

import httpx
from deepagents.backends.protocol import SandboxBackendProtocol
from pydantic import BaseModel, ConfigDict, Field

from app.core.config import settings
from app.tools.base import CoCoTool

_ENDPOINT = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
_MAX_PAGES = 12
_MIME = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg"}

_RUBRIC = """你是资深的演示文稿与版式设计审稿人。逐页检查页面截图，只找看得见的版式问题：
- 文字溢出、被截断，或超出文本框、页面边界
- 元素互相遮挡，文字压在图片或色块上难以阅读
- 对齐不齐，同类元素的位置、字号不一致
- 留白失衡：一处挤满、一处大片空白，元素贴边
- 对比度不足，文字看不清
- 残留的占位文字、乱码，图片里出现无意义的文字
每页一行，以「第 N 页：」开头；没有问题写「无明显问题」，有问题逐条写出位置和具体改法。
不评价内容写得好不好，不写总结。"""


class PageReviewInput(BaseModel):
    image_paths: list[str] = Field(
        min_length=1, max_length=_MAX_PAGES,
        description="渲染好的页面图片在工作区里的绝对路径（PNG / JPG），按页序排列",
    )
    focus: str = Field(default="", description="需要特别留意的地方，如「第 3 页刚改过表格」；没有就留空")


class PageReviewTool(CoCoTool):
    """渲染图交给视觉模型，换回逐页问题清单。"""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str = "review_pages"
    display_name: str = "检查页面效果"
    description: str = (
        "把渲染好的页面图片交给视觉模型检查版式：文字溢出、遮挡、对齐、留白、对比度，返回逐页问题清单。"
        f"一次最多 {_MAX_PAGES} 页；改过之后只需复查改过的页。"
    )
    args_schema: type[BaseModel] = PageReviewInput

    timeout_seconds: float = 180.0
    max_output_chars: int = 6000

    # ---- per-run bound field（构造时必传）----
    backend: SandboxBackendProtocol

    async def _execute(self, image_paths: list[str], focus: str = "") -> str:
        api_key = settings.DASHSCOPE_API_KEY.get_secret_value().strip()
        if not api_key:
            return "看图服务未配置，跳过这一步，按说明书做文件校验即可。"

        for path in image_paths:
            if PurePosixPath(path).suffix.lower() not in _MIME:
                return f"{path} 不是 PNG / JPG 图片，先把页面渲染成图片再检查。"

        files = await self.backend.adownload_files(image_paths)
        missing = [f.path for f in files if f.error or f.content is None]
        if missing:
            return f"读不到这些图片：{'、'.join(missing)}。确认路径是工作区里的绝对路径。"

        intro = f"共 {len(files)} 页。" + (f"特别留意：{focus}" if focus else "")
        content: list[dict] = [{"type": "text", "text": intro}]
        for page, f in enumerate(files, 1):
            mime = _MIME[PurePosixPath(f.path).suffix.lower()]
            data = base64.b64encode(f.content).decode()
            content.append({"type": "text", "text": f"第 {page} 页"})
            content.append({"type": "image_url", "image_url": {"url": f"data:{mime};base64,{data}"}})

        body = {
            "model": settings.VISION_MODEL,
            "messages": [
                {"role": "system", "content": _RUBRIC},
                {"role": "user", "content": content},
            ],
        }
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            resp = await client.post(
                _ENDPOINT, json=body, headers={"Authorization": f"Bearer {api_key}"},
            )
        if resp.status_code != 200:
            return f"检查失败：HTTP {resp.status_code}，这一步可以跳过，按说明书做文件校验。"
        choices = resp.json().get("choices") or []
        text = choices[0].get("message", {}).get("content", "") if choices else ""
        return text.strip() or "视觉模型没有返回结论，这一步可以跳过。"
