"""记忆写入工具 —— per-(user, workspace) bound 实例。

同 KnowledgeRetrievalTool 是「装配阶段实例化、不进 registry」那一类,不同的是
它连 description 都是固定的:KB 工具要靠 description 让 LLM 在多个库之间选,
而记忆只有一份、写哪儿是定死的,模型只需要决定「记什么」。

**只写工作空间那一格,写不了全局。** 全局那格的准入条件是「同一件事在他别的
工作空间也出现过」—— 这个证据本工具在结构上就拿不到(它只活在当前工作空间的
这一轮里)。让它填一个自己没有证据支撑的格子等于让它猜,而猜错的代价是那条
规矩跟着用户进入他所有的工作空间、且他查不出原因。全局那格只能由后台整理
任务从沉淀里升上去。

挂载点只有一个:supervisor。@直连的成员、被派活的成员、Playground 都不挂
(见 workspace.build_workspace_graph)。
"""

from uuid import UUID

from pydantic import BaseModel, Field

from app.services.memory import MemoryService
from app.tools.base import CoCoTool, ToolSourceType

_DESCRIPTION = """把用户在这个工作空间的长期偏好记下来,以后每一轮对话都会带着它。

**整段覆写,不是追加。** content 要写这段记忆的**完整新版本**:仍然成立的旧内容
照抄,再把这次要加的加上、要改的改掉。只传一句新的,旧的会全部消失。
当前记忆的原文就在你系统提示的「记忆」一节里(还没有就是空的)。

什么时候调:
- 用户明说要你记住(「记住」「以后都这样」「别再问我了」)
- 你正打算回「好的我记住了」这类话 —— 先调这个,再回
- 用户第二次、第三次纠正你同一件事

什么时候不调:
- 用户只是这一次这么要求。一次不算习惯
- 你自己观察出来的规律 —— 你的推测不是事实,写进去它就成事实了
- 下次就不成立的东西(当前文件名、这一轮的结果),那些聊天记录里有

写成用户自己读得懂的话,他会在界面上看到原文。别写「用户偏好于」这种腔调。"""


class MemoryUpdateInput(BaseModel):
    content: str = Field(
        ..., description="这个工作空间记忆的完整新版本(不是要追加的那一句)"
    )


class MemoryUpdateTool(CoCoTool):
    """覆写当前用户在当前工作空间的常驻记忆。"""

    name: str = "update_memory"
    display_name: str = "更新记忆"
    description: str = _DESCRIPTION
    source_type: ToolSourceType = "memory"
    args_schema: type[BaseModel] = MemoryUpdateInput

    # 回执只有一句话,不需要 4000 字的额度
    max_output_chars: int = 200

    # ---- per-instance bound fields(构造时必传)----
    user_id: UUID
    workspace_id: UUID

    async def _execute(self, content: str) -> str:
        await MemoryService().save_workspace_scope(
            workspace_id=self.workspace_id, user_id=self.user_id, content=content
        )
        # 回执带字数:整段覆写最大的风险是模型把旧内容弄丢,而它自己看不见结果。
        # 报一个字数,它能当场察觉「我刚才那段怎么才二十个字」
        return f"已更新这个工作空间的记忆,现在共 {len(content)} 字。"
