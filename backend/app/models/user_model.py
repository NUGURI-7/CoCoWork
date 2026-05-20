from tortoise import fields

from app.models.base import TimestampMixin, UUIDBaseModel


class User(UUIDBaseModel, TimestampMixin):
    """用户实体。

    - `username`：登录凭证，业务唯一标识
    - `email`：注册必填，仅用于密码重置 / 邮件通知，不参与登录
    - `password_hash`：密码 hash（默认 argon2，~96 字符）；明文密码绝不入库
    - `nick_name`：UI 显示用，注册不填则保持空字符串
    - `is_active`：账户启用状态；False 视为封禁/注销，鉴权时需检查
    - `is_admin`：管理员标记；预留位，实际权限模型在 RBAC 阶段细化
    """

    username = fields.CharField(max_length=20, unique=True, description="用户名（登录凭证）")
    email = fields.CharField(max_length=255, unique=True, description="邮箱（注册必填）")
    password_hash = fields.CharField(max_length=255, description="密码哈希")
    nick_name = fields.CharField(max_length=50, default="", description="昵称（显示用）")
    avatar_url = fields.CharField(max_length=512, default="", description="头像 URL")
    is_active = fields.BooleanField(default=True, description="账户是否启用")
    is_admin = fields.BooleanField(default=False, description="管理员标记")

    class Meta:
        table = "users"
