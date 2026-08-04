from uuid import UUID

from tortoise.exceptions import IntegrityError
from tortoise.expressions import Q

from app.core.exceptions.types import (
    AppAuthenticationFailed,
    NotFound404,
    ValidationException,
)
from app.core.security import create_access_token, get_password_hash, verify_password
from app.models.user import User
from app.schemas.user import UserLogin, UserRegister


class UserService:
    """用户业务逻辑：注册 / 登录 / 查询。

    不挂任何全局状态。路由通过 `Depends(get_user_service)`（D1 后段在 depends.py
    定义）拿到实例。当前无依赖；未来加 Email / Redis / 审计服务等时通过 __init__ 注入。
    """

    async def register(self, data: UserRegister) -> User:
        """创建新用户，username 和 email 都需唯一。

        预检查 + DB unique 约束双重保险：预检查给出友好错误，
        IntegrityError 兜住并发场景下两个请求同时通过预检查的竞态。
        """
        if await User.filter(username=data.username).exists():
            raise ValidationException(f"用户名 {data.username} 已被使用")
        if await User.filter(email=data.email).exists():
            raise ValidationException(f"邮箱 {data.email} 已被注册")

        try:
            return await User.create(
                username=data.username,
                email=data.email,
                password_hash=get_password_hash(data.password),
                nick_name=data.nick_name,
            )
        except IntegrityError as e:
            raise ValidationException("用户名或邮箱已被使用") from e

    async def authenticate(self, username: str, password: str) -> User:
        """校验 username + password；失败统一抛 AppAuthenticationFailed。

        "用户名不存在" 与 "密码错误" 故意返回同样的错误消息，
        防止攻击者通过响应差异枚举有效用户名。
        """
        user = await User.filter(username=username).first()
        if user is None or not verify_password(password, user.password_hash):
            raise AppAuthenticationFailed("用户名或密码错误")
        if not user.is_active:
            raise AppAuthenticationFailed("账户已被禁用")
        return user

    async def login(self, data: UserLogin) -> dict:
        """authenticate 通过后签发 access token；返回 dict 由 route 层包成 TokenOut。"""
        user = await self.authenticate(data.username, data.password)
        access_token = create_access_token(data={"sub": str(user.id)})
        return {"access_token": access_token, "user": user}

    async def get_user_by_id(self, user_id: UUID) -> User | None:
        """按 id 查 User，不存在返回 None（不抛异常 —— 调用方决定怎么处理）。"""
        return await User.filter(id=user_id).first()

    async def list_all(self, *, keyword: str = "", only_admin: bool | None = None) -> list[User]:
        """全量列出用户，供管理员后台用。

        **不分页**：真实产品的用户列表一定分页，这里没做，因为本项目用户数是个位数。
        要加的时候照 `routes/workspace/artifact.py` 那套 limit/offset 补即可。

        keyword 同时匹配用户名 / 邮箱 / 昵称 —— 管理员记得住哪个就用哪个搜，
        没必要让他先想清楚自己记的是哪一栏。
        """
        qs = User.all()
        if keyword:
            qs = qs.filter(
                Q(username__icontains=keyword)
                | Q(email__icontains=keyword)
                | Q(nick_name__icontains=keyword)
            )
        if only_admin is not None:
            qs = qs.filter(is_admin=only_admin)
        return await qs.order_by("-created_at")

    async def set_active(self, target_id: UUID, *, is_active: bool, operator: User) -> User:
        """管理员启用 / 停用某个账户。

        **禁止操作自己**，这不是防手滑的体贴：停用之后连登录都进不来
        （`authenticate` 里 `is_active` 为假直接拒），如果他是最后一个管理员，
        就再没有人能把它改回来了。前端那行虽然已置灰，但改个 URL 就绕过去了 ——
        真正算数的拦截只能在这里。
        """
        if target_id == operator.id:
            raise ValidationException("不能停用自己的账户")

        target = await User.filter(id=target_id).first()
        if target is None:
            raise NotFound404("用户不存在")

        if target.is_active != is_active:
            target.is_active = is_active
            await target.save(update_fields=["is_active", "updated_at"])
        return target


async def get_user_service() -> UserService:
    """FastAPI 依赖：返回 UserService 实例。

    当前 UserService 无状态、无依赖，每次返回新实例的开销可忽略。
    未来注入 Email / Redis / 审计服务等依赖时，这里集中改造。
    """
    return UserService()
