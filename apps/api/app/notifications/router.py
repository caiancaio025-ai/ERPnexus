from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.auth.router import current_user
from app.core.db import get_db
from app.notifications.models import Notification
from app.notifications.schemas import NotificationOutput, NotificationSummary

router = APIRouter(prefix="/notifications")
CurrentUser = Annotated[User, Depends(current_user)]
DbSession = Annotated[AsyncSession, Depends(get_db)]


@router.get("", response_model=NotificationSummary)
async def list_notifications(
    user: CurrentUser,
    db: DbSession,
    limit: int = Query(default=12, ge=1, le=50),
):
    unread_count = int(
        await db.scalar(
            select(func.count(Notification.id)).where(
                Notification.user_id == user.id,
                Notification.is_read.is_(False),
            )
        )
        or 0
    )
    items = list(
        (
            await db.scalars(
                select(Notification)
                .where(Notification.user_id == user.id)
                .order_by(Notification.created_at.desc(), Notification.id.desc())
                .limit(limit)
            )
        ).all()
    )
    return NotificationSummary(unread_count=unread_count, items=items)


@router.post("/{notification_id}/read", response_model=NotificationOutput)
async def mark_read(notification_id: int, user: CurrentUser, db: DbSession):
    item = await db.scalar(
        select(Notification).where(Notification.id == notification_id, Notification.user_id == user.id)
    )
    if not item:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Notificação não encontrada.")
    if not item.is_read:
        item.is_read = True
        item.read_at = datetime.now(UTC)
        await db.commit()
        await db.refresh(item)
    return item


@router.post("/read-all")
async def mark_all_read(user: CurrentUser, db: DbSession):
    await db.execute(
        update(Notification)
        .where(Notification.user_id == user.id, Notification.is_read.is_(False))
        .values(is_read=True, read_at=datetime.now(UTC))
    )
    await db.commit()
    return {"ok": True}
