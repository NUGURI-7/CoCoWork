"""内置工具：sleep —— 异步等待指定秒数，测试 / 演示用。

必须用 asyncio.sleep 而非 time.sleep：后者同步阻塞整个事件循环，
睡 n 秒期间所有并发请求全部冻结；前者把控制权交还事件循环、零阻塞。

入参上限钉在基类 timeout_seconds（30s）之下 —— 超过它只会被超时兜底
吃掉返回超时文案，不存在有意义的更大值。
"""

import asyncio

from pydantic import BaseModel, Field

from app.tools.base import CoCoTool
from app.tools.registry import register_tool

_MAX_SECONDS = 25.0


class SleepInput(BaseModel):
    seconds: float = Field(
        ...,
        gt=0,
        le=_MAX_SECONDS,
        description=f"等待的秒数，范围 (0, {_MAX_SECONDS:g}]，支持小数。",
    )


@register_tool
class SleepTool(CoCoTool):
    name: str = "sleep"
    display_name: str = "睡觉"
    description: str = (
        "等待指定秒数后返回。当用户明确要求等待 / 暂停 / 睡觉一段时间时使用，"
        "其他场景不要调用。"
    )
    args_schema: type[BaseModel] = SleepInput

    async def _execute(self, seconds: float) -> str:
        await asyncio.sleep(seconds)
        return f"睡了 {seconds:g} 秒，已醒。"
