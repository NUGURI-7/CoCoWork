"""交付区清单解析单测 —— 「哪些文件是产物」的全部答案就是这一次 ls。

这层的失败必须是**返回空**而不是抛异常：产物是回复的附赠品，为它炸掉一次
已经完成的对话是本末倒置（artifact.py 文件头写的失败策略）。所以这里大半
用例考的是「烂输入不要炸」。
"""

import json

import pytest

from app.services.sandbox.artifact import _list_delivery, human_size
from tests.sandbox_fakes import FakeBackend


async def test_parses_name_and_size_pairs():
    backend = FakeBackend(output=json.dumps([["chart.svg", 3598], ["data.json", 120]]))

    assert await _list_delivery(backend, "/outputs/abc") == [
        ("chart.svg", 3598),
        ("data.json", 120),
    ]


async def test_empty_delivery_is_not_an_error():
    """挂了 skill 但这轮没产出，是常态不是故障。"""
    assert await _list_delivery(FakeBackend(output="[]"), "/outputs/abc") == []


async def test_missing_directory_is_not_an_error():
    """交付区不存在（没起容器）—— 命令里已经吞了 stderr，输出是空串。"""
    assert await _list_delivery(FakeBackend(output=""), "/outputs/abc") == []


async def test_nonzero_exit_returns_empty():
    assert await _list_delivery(FakeBackend(output="boom", exit_code=1), "/outputs/x") == []


@pytest.mark.parametrize("garbage", ["not json", "{}", '[["only-name"]]', "null"])
async def test_garbage_output_returns_empty_instead_of_raising(garbage: str):
    """沙箱里跑的是用户的代码，它往 stdout 里吐什么都有可能。"""
    assert await _list_delivery(FakeBackend(output=garbage), "/outputs/x") == []


async def test_path_goes_through_base64_not_shell_quoting():
    """路径走 base64 塞进命令 —— 文件名里的引号空格搅不烂 shell 引用规则。"""
    backend = FakeBackend(output="[]")
    await _list_delivery(backend, "/outputs/abc")

    assert "/outputs/abc" not in backend.commands[0]  # 明文不出现在命令里
    assert "base64.b64decode" in backend.commands[0]


# ---------- human_size：模型判断「这文件大不大」全靠它 ----------

@pytest.mark.parametrize(
    ("size", "expected"),
    [(0, "0B"), (1023, "1023B"), (1024, "1KB"), (12345, "12KB"), (1024 * 1024, "1.0MB")],
)
def test_human_size(size: int, expected: str):
    assert human_size(size) == expected
