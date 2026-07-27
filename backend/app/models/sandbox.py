"""沙箱产物 —— agent 在一轮回复里交付给用户的文件。

「哪些文件算产物」不靠扫描、不靠比对：沙箱里有一个**每轮新建的交付区目录**，
放进去的就是产物（设计稿 C.1 / C.2）。一轮结束 `ls` 那个目录，逐个收进对象存储、
在本表落一条记录。目录是空的开始的，所以里面有什么就是什么。

本表存在的理由有两个，缺一不可：

1. **回放** —— 容器早销毁了、SSE 帧也消费完了。用户三天后翻回那条消息，
   卡片还能不能渲染、还能不能点下载，全靠这张表。
2. **鉴权** —— 下载接口凭 `created_by` 一条 SQL 判断归属，而不是从 URL 拼路径
   去磁盘上找。归属条件进得了 WHERE，就不存在「查到了但忘了判权限」这个状态。

存储形态沿用 Document / Skill：**表存元数据 + 对象存储的 key，字节走 storage 抽象**。
"""

from tortoise import fields

from app.models.base import TimestampMixin, UUIDBaseModel


class SandboxArtifact(UUIDBaseModel, TimestampMixin):
    """一轮回复交付出来的一个文件。"""

    created_by = fields.ForeignKeyField(
        "models.User",
        related_name="sandbox_artifacts",
        on_delete=fields.CASCADE,
        db_index=True,
        description="产物归属人。下载鉴权走它——Playground 与 workspace 两条路都有值",
    )
    conversation = fields.ForeignKeyField(
        "models.Conversation",
        related_name="sandbox_artifacts",
        null=True,
        on_delete=fields.CASCADE,
        db_index=True,
        description="workspace 对话产出的填此项；Playground 无对话，为 NULL",
    )
    message_id = fields.UUIDField(
        db_index=True,
        description="产出它的那条 assistant 消息 ID。刻意不做外键——Playground 的消息不入库，做了 FK 就插不进来",
    )
    filename = fields.CharField(
        max_length=255,
        description="交付区里的文件名，也是下载时给浏览器的名字",
    )
    size = fields.IntField(description="字节数")
    content_type = fields.CharField(
        max_length=128,
        description="由扩展名推出的 MIME 类型；下载接口据此决定浏览器内联渲染还是另存",
    )
    storage_key = fields.CharField(
        max_length=512,
        description="对象存储的键：sandbox/{scope_id}/{message_id}/{filename}",
    )

    class Meta:
        table = "sandbox_artifacts"
        # 一条消息的产物来自同一个交付区目录，文件名天然唯一。
        # 把这条已知约束写进数据库，重复收产物会被挡下而不是插出两条。
        unique_together = (("message_id", "filename"),)