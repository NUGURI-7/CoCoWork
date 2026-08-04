from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserRegister(BaseModel):
    """注册请求体。"""

    username: str = Field(
        min_length=3,
        max_length=20,
        pattern=r"^[a-zA-Z0-9_]+$",
        description="字母 / 数字 / 下划线，3-20 字符",
    )
    email: EmailStr = Field(description="邮箱，用于密码重置 / 通知")
    password: str = Field(min_length=6, max_length=64, description="密码")
    nick_name: str = Field(min_length=2, max_length=50, description="昵称（必填）")


class UserLogin(BaseModel):
    """登录请求体（用 username + 密码）。"""

    username: str = Field(min_length=3, max_length=20)
    password: str = Field(min_length=6, max_length=64)


class UserOut(BaseModel):
    """用户对外公开信息。"""

    id: UUID
    username: str
    email: EmailStr
    nick_name: str
    avatar_url: str
    is_active: bool
    is_admin: bool
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class TokenOut(BaseModel):
    """登录成功响应：token + 当前用户信息。"""

    access_token: str
    token_type: str = "bearer"
    user: UserOut


class UserStatusIn(BaseModel):
    """管理员启用 / 停用某个账户。

    只有 `is_active` 一个字段 —— 改角色（`is_admin`）不走这个接口。两件事轻重
    完全不同，合进同一个 PATCH，前端一次多传就可能连带升权。
    """

    is_active: bool
