from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.access import user_can_create_quote, user_has_module
from app.auth.models import User
from app.notifications.models import Notification


async def notify_modules(
    db: AsyncSession,
    *,
    modules: set[str],
    category: str,
    title: str,
    message: str,
    target: str | None = None,
    severity: str = "info",
    entity_type: str | None = None,
    entity_id: int | None = None,
    work_order_id: int | None = None,
    amount: Decimal | None = None,
    exclude_user_id: int | None = None,
) -> None:
    users = list((await db.scalars(select(User).where(User.is_active.is_(True)))).all())
    for user in users:
        if exclude_user_id is not None and user.id == exclude_user_id:
            continue
        if user.role in {"super_admin", "admin"} or any(
            user_has_module(user.role, user.modules, module) for module in modules
        ):
            db.add(
                Notification(
                    user_id=user.id,
                    category=category,
                    severity=severity,
                    title=title,
                    message=message,
                    target=target,
                    entity_type=entity_type,
                    entity_id=entity_id,
                    work_order_id=work_order_id,
                    amount=amount,
                )
            )


async def notify_quote_users(
    db: AsyncSession,
    *,
    category: str,
    title: str,
    message: str,
    target: str | None = None,
    severity: str = "info",
    entity_type: str | None = None,
    entity_id: int | None = None,
    work_order_id: int | None = None,
    exclude_user_id: int | None = None,
) -> None:
    """Notify only active users authorized to create/emit quotes."""
    users = list((await db.scalars(select(User).where(User.is_active.is_(True)))).all())
    for user in users:
        if exclude_user_id is not None and user.id == exclude_user_id:
            continue
        if user_can_create_quote(user.role, user.modules):
            db.add(Notification(
                user_id=user.id,
                category=category,
                severity=severity,
                title=title,
                message=message,
                target=target,
                entity_type=entity_type,
                entity_id=entity_id,
                work_order_id=work_order_id,
            ))
