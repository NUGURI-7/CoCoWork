"""安全工具：JWT 签发/校验、密码哈希。"""

from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from jwt import ExpiredSignatureError, InvalidTokenError
from passlib.context import CryptContext

from app.core.config import settings
from app.core.exceptions.types import AppAuthenticationFailed

# Argon2 主推（PHC 2015 获胜算法，抗 GPU 暴力破解），bcrypt 兼容遗留 hash。
# deprecated="auto" 让 verify 时自动识别旧算法，需要时调用方可用 verify_and_update 升级。
pwd_context = CryptContext(schemes=["argon2", "bcrypt"], deprecated="auto")


def create_access_token(
    data: dict[str, Any],
    expires_delta: timedelta | None = None,
) -> str:
    """生成 JWT access token。

    Args:
        data: 业务声明（claims）。约定 `sub` 放用户 id（字符串），其余字段任意。
        expires_delta: 自定义有效期，缺省时用 settings.ACCESS_TOKEN_EXPIRE_MINUTES。
    """
    now = datetime.now(timezone.utc)
    expire = now + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    payload: dict[str, Any] = {**data, "iat": now, "exp": expire}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def verify_token(token: str) -> dict[str, Any]:
    """解码并校验 JWT。

    过期 / 签名错误 / 格式非法 都抛 AppAuthenticationFailed，
    由全局异常处理器统一翻译成 401 响应。
    """
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except ExpiredSignatureError as e:
        raise AppAuthenticationFailed("登录已过期") from e
    except InvalidTokenError as e:
        raise AppAuthenticationFailed("无效的登录凭证") from e


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """校验密码。不抛异常，True/False 由调用方处理。"""
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(plain_password: str) -> str:
    """生成密码 hash。新用户注册时使用，默认走 argon2。"""
    return pwd_context.hash(plain_password)
