"""运行时资源的可用规则 —— 「这个人能不能用这份知识库 / Skill / MCP / 模型」都走这里。

能用 = 自己建的 + 管理员建的。管理员建的视为公司公共资源，所有人运行时可用。
管理（列表 / 编辑 / 删除）不走这里，仍只限创建者。
"""

from tortoise.expressions import Q

from app.models import User


def usable_by(user: User, owner: str = "created_by") -> Q:
    """owner 是指向资源创建者的字段路径；模型挂在供应商下，传 "provider__created_by"。"""
    return Q(**{owner: user}) | Q(**{f"{owner}__is_admin": True})
