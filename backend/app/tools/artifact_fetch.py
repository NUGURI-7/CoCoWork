"""取回历史产物的工具 —— 把之前交付过的文件重新放回工作区。

**为什么需要它**：容器一次性，每轮的 `/workspace` 都是全新的空目录（决策 14a）。
上一轮产出的文件活在对象存储里，模型在历史的 `<artifacts>` 标注里看得见它，
但容器里没有 —— 这个工具就是那座桥。

**per-run bound 实例**，形态同 KnowledgeRetrievalTool：构造时绑本轮的 backend 与
conversation，装配阶段实例化，不进 registry（离开沙箱它毫无意义，不该让用户去勾）。
"""

import shlex
from uuid import UUID

from deepagents.backends.protocol import SandboxBackendProtocol
from pydantic import BaseModel, ConfigDict, Field
from tortoise.expressions import Q

from app.core.storage import storage
from app.models.sandbox import SandboxArtifact
from app.services.sandbox.artifact import human_size
from app.tools.base import CoCoTool

_DESCRIPTION = """把本对话之前出现过的文件取回工作区。

历史消息里 <artifacts>（agent 产出的）和 <attachments>（用户附上的）标注过的文件
**都不在当前工作区** —— 每一轮的工作区都是全新的空目录。要接着用它们
（在上次那张图上改、读上次那份数据），必须先用本工具取回来。

传文件名即可，与标注里写的一致；取回后会告诉你它的绝对路径。"""


class ArtifactFetchInput(BaseModel):
    filename: str = Field(
        ...,
        description="要取回的文件名，与历史消息 <artifacts> / <attachments> 里标注的一致",
    )


class ArtifactFetchTool(CoCoTool):
    """取回本对话的历史产物（决策 24）。"""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str = "fetch_artifact"
    display_name: str = "取回历史产物"
    description: str = _DESCRIPTION
    args_schema: type[BaseModel] = ArtifactFetchInput

    # 拉一个 20MB 的产物 + 灌进容器，30 秒的默认值不够宽
    timeout_seconds: float = 60.0
    max_output_chars: int = 500  # 返回就一句话，用不着 4000

    # ---- per-run bound fields（构造时必传）----
    # 三个边界字段全部服务端注入，绝不接受模型输入
    backend: SandboxBackendProtocol  # 本轮的执行后端 —— 只有它够得着工作区
    workspace_dir: str  # paths.workspace，值由 driver 决定，不是常量
    conversation_id: UUID  # 本对话产出的产物，全部可取
    user_id: UUID  # 归属人，进 WHERE —— 这一层不依赖「别处已经校过了」
    referenced_artifact_ids: frozenset[UUID] = frozenset()
    """本对话历史里被拖进来引用过的产物（决策 25）。它们属于**别的**对话，
    但既然模型在这条对话的 <attachments> 标注里看得见，就该取得回来 ——
    否则就是决策 24 明确不要的那种「看得见、取不回」。"""

    async def _execute(self, filename: str) -> str:
        # 取值范围 = 本对话产出的 ∪ 本对话拖进来引用过的（决策 24 + 25）。
        # 两者合起来**恰好等于**模型在这条对话历史里看得见的文件：
        # <artifacts> 标的是前者、<attachments> 标的是后者，多一个都取不到（最小权限）
        scope = Q(conversation_id=self.conversation_id)
        if self.referenced_artifact_ids:
            # 空集合不能进 id__in —— 那会拼出 `IN ()`，各数据库表现还不一样
            scope |= Q(id__in=list(self.referenced_artifact_ids))

        # 边界条件全进 WHERE，不存在「查到了但忘了判权限」这个中间状态
        artifacts = await SandboxArtifact.filter(
            scope, created_by_id=self.user_id, filename=filename
        ).order_by("-created_at")

        if not artifacts:
            # 错误要可执行：告诉它去哪儿找正确的名字，而不是只说一句「没有」
            return (
                f"取不到「{filename}」。"
                "能取的只有历史消息里 <artifacts> / <attachments> 标注过的，"
                "请照那上面的名字重试。"
            )

        artifact = artifacts[0]  # 同名取最新 —— 「刚才那张图」几乎总是最新的那个
        target = f"{self.workspace_dir}/{filename}"

        # 已存在就不覆盖：这一轮的脚本可能刚写了个同名文件，拿旧版本冲掉它是灾难。
        # 而且既然已经在，模型要的多半就是它。test -e 是 POSIX，两个 driver 都有
        probe = await self.backend.aexecute(f"test -e {shlex.quote(target)}")
        if probe.exit_code == 0:
            return f"{target} 已经在工作区里了，直接用即可（本工具未覆盖它）。"

        content = await storage.read(artifact.storage_key)
        responses = await self.backend.aupload_files([(target, content)])
        error = responses[0].error if responses else "上传没有返回结果"
        if error:
            return f"取回「{filename}」失败：{error}"

        # 同名不再只可能来自本对话 —— 拖进来的那些属于别的对话（决策 25），
        # 说「本对话有 N 个」就不准了。模型是读这句话判断要不要追问的，得说准
        dup = (
            f"（能取到的文件里有 {len(artifacts)} 个都叫这个名字，这是最新的那个；"
            "要的不是它就说清是哪一次产出的）"
            if len(artifacts) > 1 else ""
        )
        return f"已取回 {target}（{human_size(artifact.size)}）{dup}"
