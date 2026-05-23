from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.depends import get_current_user
from app.core.http import ResponseModel, success
from app.models.user import User
from app.schemas.user import TokenOut, UserLogin, UserOut, UserRegister
from app.services.user import UserService, get_user_service

router = APIRouter(prefix="/users", tags=["users"])

# 类型别名，复用 Depends 声明
UserServiceDep = Annotated[UserService, Depends(get_user_service)]
CurrentUserDep = Annotated[User, Depends(get_current_user)]


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
