"""常驻记忆数据模型 —— 跨会话长期记忆的第一层。

两张表 = 两个尺度,各存一段纯文字,原地覆写:
- UserMemory:      这个人是谁(换工作区照样成立),一个用户一份
- WorkspaceMemory: 这个人在这个工作区的偏好与约定(只在本区成立),一人一区一份

**为什么是两张表,不是一张带 scope 列的表**:一张表得靠「workspace_id 为空
= 用户级」来区分尺度,而唯一约束里 NULL 之间互不相等 —— 数据库拦不住同一个
用户存出好几行用户级记忆。要拦就得写部分唯一索引,那只能手写迁移 SQL。
拆成两张,唯一性直接落在各自的键上,CLI 生成的迁移天然带着。

**为什么不存历史版本**:常驻记忆是压缩产物,原始记录(messages 表)一直都在,
压错了回去翻原文即可。与 ConversationSummary 的 append-only 刻意相反 ——
那张表的旧行有用(压缩比曲线直接查表),这张的旧行没有用途。

**字数上限为什么不进表**:它是全局常量,不给用户调 —— 调大直接抬高每一轮的
prompt 成本,而用户没有判断依据。放代码里一处改,不用迁移。
"""

from tortoise import fields

from app.models.base import TimestampMixin, UUIDBaseModel


class UserMemory(UUIDBaseModel, TimestampMixin):
    """一个用户一份的全局常驻记忆。"""

    user = fields.OneToOneField(
        "models.User", related_name="memory", on_delete=fields.CASCADE,
        description="归属用户 —— OneToOne 保证一人一份",
    )
    content = fields.TextField(
        default="", description="记忆正文(成品,直接拼进 system prompt)"
    )

    class Meta:
        table = "user_memories"


class WorkspaceMemory(UUIDBaseModel, TimestampMixin):
    """一个人在一个工作区里的局部常驻记忆。

    唯一键是 (workspace, user) 而不是 workspace 单列:主语是**人**,记的是
    「这个人在这个区的偏好与约定」。今天工作区只有一个归属人(created_by),
    两种写法效果一样;但工作区一旦能转手或共享,单列唯一就是错的,而且那时
    补 user 列要连数据回填一起做。

    转手场景下这一列**刻意与 workspace.created_by 脱钩**:记忆属于形成它的
    那个人,新接手的人不继承前一个人的偏好 —— 两边不一致正是要的行为。

    两个外键的索引待遇不同:workspace 不单独建索引(复合唯一索引的最左前缀
    就是它,按 workspace 查已经走得上,再建一个是重复索引);user 必须显式加
    (它不是最左前缀,反查与级联删都得靠自己这个索引,否则走 Seq Scan)。
    """

    workspace = fields.ForeignKeyField(
        "models.Workspace", related_name="memories", on_delete=fields.CASCADE,
        description="所属工作区",
    )
    user = fields.ForeignKeyField(
        "models.User", related_name="workspace_memories", on_delete=fields.CASCADE,
        db_index=True, description="记忆属于谁",
    )
    content = fields.TextField(
        default="", description="记忆正文(成品,直接拼进 system prompt)"
    )

    class Meta:
        table = "workspace_memories"
        unique_together = (("workspace", "user"),)
