"""清理过期的临时账号：先删对象存储里的产物，再删账号（数据库级联带走其余数据）。"""

import logging
from datetime import datetime, timedelta, timezone

from app.core.config import settings
from app.core.storage import storage
from app.models import User, Workspace

logger = logging.getLogger(__name__)

PURGE_BATCH = 200


async def purge_expired_guests() -> int:
    cutoff = datetime.now(timezone.utc) - timedelta(days=settings.DEMO_GUEST_RETENTION_DAYS)
    guests = await User.filter(is_guest=True, created_at__lt=cutoff).limit(PURGE_BATCH)
    for guest in guests:
        await _purge_guest(guest)
    return len(guests)


async def _purge_guest(user: User) -> None:
    workspace_ids = await Workspace.filter(created_by=user).values_list("id", flat=True)
    for scope_id in (user.id, *workspace_ids):
        await storage.delete_prefix(f"sandbox/{scope_id}/")
    await user.delete()
