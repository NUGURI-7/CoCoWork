from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from app.core.depends import get_current_admin, get_current_user
from app.core.http import ResponseModel, success
from app.models.user import User
from app.schemas.user import TokenOut, UserLogin, UserOut, UserRegister, UserStatusIn
from app.services.user import UserService, get_user_service

router = APIRouter(prefix="/users", tags=["users"])

# 类型别名，复用 Depends 声明
UserServiceDep = Annotated[UserService, Depends(get_user_service)]
CurrentUserDep = Annotated[User, Depends(get_current_user)]
AdminDep = Annotated[User, Depends(get_current_admin)]


@router.post("/register", summary="用户注册")
async def register(
    data: UserRegister,
    user_service: UserServiceDep,
) -> ResponseModel[UserOut]:
    user = await user_service.register(data)
    return success(data=UserOut.model_validate(user), message="注册成功")


@router.post("/login", summary="用户登录")
async def login(
    data: UserLogin,
    user_service: UserServiceDep,
) -> ResponseModel[TokenOut]:
    result = await user_service.login(data)
    return success(
        data=TokenOut(
            access_token=result["access_token"],
            user=UserOut.model_validate(result["user"]),
        )
    )


@router.get("/me", summary="获取当前用户")
async def read_me(current_user: CurrentUserDep) -> ResponseModel[UserOut]:
    return success(data=UserOut.model_validate(current_user))


@router.get("", summary="用户列表（管理员）")
async def list_users(
    user_service: UserServiceDep,
    _: AdminDep,
    keyword: str = Query(default="", max_length=50, description="按用户名 / 邮箱 / 昵称模糊搜"),
    only_admin: bool | None = Query(default=None, description="按角色筛选；不传 = 不筛"),
) -> ResponseModel[list[UserOut]]:
    users = await user_service.list_all(keyword=keyword, only_admin=only_admin)
    return success(data=[UserOut.model_validate(u) for u in users])


@router.patch("/{user_id}/status", summary="启用 / 停用账户（管理员）")
async def set_user_status(
    user_id: UUID,
    data: UserStatusIn,
    user_service: UserServiceDep,
    admin: AdminDep,
) -> ResponseModel[UserOut]:
    user = await user_service.set_active(user_id, is_active=data.is_active, operator=admin)
    return success(data=UserOut.model_validate(user), message="已更新账户状态")
