"""sandboxd 的线上格式 —— web 与 sandboxd 之间的契约。

**放在 app/sandbox/ 而不是 app/schemas/**：这不是对外 API 的 schema，是两个内部
进程之间的私有协议。而且 web 侧的客户端也 import 这里 —— 一份定义两边共用，
改字段时不会漏掉一边。

上传 / 下载没有对应的模型：它们的 body 是**裸 tar 字节**而非 JSON，套不进
pydantic；目标路径走 query 参数。
"""

from pydantic import BaseModel, Field


class OpenSessionRequest(BaseModel):
    """建会话 = 起一个容器。"""

    env: dict[str, str] = Field(
        default_factory=dict,
        description="注入容器的环境变量，含解密后的 skill 凭据（决策 15）",
    )


class OpenSessionResponse(BaseModel):
    session_id: str


class ExecRequest(BaseModel):
    command: str
    timeout: int = Field(gt=0, le=600, description="秒；上限与 mount 那侧保持一致")


class ExecResponse(BaseModel):
    """字段形状对齐 deepagents 的 ExecuteResponse —— web 侧原样转交，不做翻译。"""

    output: str  # stdout 与 stderr 合并，顺序即真实输出顺序
    exit_code: int
    truncated: bool


class DownloadRequest(BaseModel):
    path: str = Field(description="容器内的绝对路径，文件或目录都行")
