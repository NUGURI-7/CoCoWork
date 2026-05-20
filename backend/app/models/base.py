"""Tortoise ORM 模型抽象基类与公共 mixin。"""

import uuid_utils.compat as uuid_compat
from tortoise import fields, models


class UUIDBaseModel(models.Model):
    """UUID7 主键抽象基类。

    用 UUID7（自带时间序）而非 UUID4：
    - B-tree 索引更友好，避免随机插入导致页分裂
    - 时间排序天然有序，对 created_at 索引可以省略部分场景
    - `uuid_utils.compat.uuid7()` 返回标准库 UUID 对象，Tortoise UUIDField 直接兼容

    所有业务实体继承此类，统一主键风格。
    """

    id = fields.UUIDField(pk=True, default=uuid_compat.uuid7)

    class Meta:
        abstract = True


class TimestampMixin:
    """`created_at` + `updated_at` 自动时间戳。

    与 `UUIDBaseModel` 组合使用：
        class Foo(UUIDBaseModel, TimestampMixin):
            ...
    """

    created_at = fields.DatetimeField(auto_now_add=True, description="创建时间")
    updated_at = fields.DatetimeField(auto_now=True, description="更新时间")
