from datetime import UTC, datetime, date, time, timedelta
from zoneinfo import ZoneInfo
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import case, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.access import user_can_view_sensitive_values
from app.auth.models import User
from app.auth.router import current_user
from app.core.db import get_db
from app.notifications.models import Notification
from app.notifications.schemas import NotificationOutput, NotificationSummary, NotificationHistory
from app.notifications.service import MODULES, activity_visible

router = APIRouter(prefix="/notifications")
CurrentUser = Annotated[User, Depends(current_user)]
DbSession = Annotated[AsyncSession, Depends(get_db)]


def _notification_output(item: Notification, *, include_sensitive_values: bool) -> NotificationOutput:
    output = NotificationOutput.model_validate(item)
    if not include_sensitive_values:
        output.amount = None
    return output


_LEGACY_SQL_MODULE = case(
    (Notification.category.in_(("quote", "commercial_sale_approved")), "orcamentos"),
    (Notification.category.in_(("purchase", "purchase_request", "material_request_approved")), "compras"),
    (Notification.category.in_(("finance", "financeiro", "billing")), "financeiro"),
    else_=None,
)
_EFFECTIVE_MODULE = func.coalesce(Notification.activity_module, _LEGACY_SQL_MODULE)


def _visible_predicate(user: User):
    allowed = [module for module in MODULES if activity_visible(user.role, user.modules, module)]
    return _EFFECTIVE_MODULE.in_(allowed) if allowed else _EFFECTIVE_MODULE.is_(None) & (Notification.id == -1)


def _module_for_instance(item: Notification) -> str | None:
    from app.notifications.service import visible_notification_module
    return visible_notification_module(item)


@router.get("", response_model=NotificationSummary)
async def list_notifications(
    user: CurrentUser,
    db: DbSession,
    limit: int = Query(default=12, ge=1, le=50),
    unread_only: bool = Query(default=False),
):
    visible = _visible_predicate(user)
    unread_count = int(await db.scalar(
        select(func.count(Notification.id)).where(
            Notification.user_id == user.id, visible, Notification.is_read.is_(False)
        )
    ) or 0)
    item_query = select(Notification).where(Notification.user_id == user.id, visible)
    if unread_only:
        item_query = item_query.where(Notification.is_read.is_(False))
    items = list(
        (
            await db.scalars(
                item_query
                .order_by(Notification.created_at.desc(), Notification.id.desc())
                .limit(limit)
            )
        ).all()
    )
    include_values = user_can_view_sensitive_values(user.role)
    return NotificationSummary(
        unread_count=unread_count,
        items=[_notification_output(item, include_sensitive_values=include_values) for item in items],
    )


@router.post("/{notification_id}/read", response_model=NotificationOutput)
async def mark_read(notification_id: int, user: CurrentUser, db: DbSession):
    item = await db.scalar(
        select(Notification).where(Notification.id == notification_id, Notification.user_id == user.id)
    )
    if not item or not activity_visible(user.role, user.modules, _module_for_instance(item)):
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Notificação não encontrada.")
    if not item.is_read:
        item.is_read = True
        item.read_at = datetime.now(UTC)
        await db.commit()
        await db.refresh(item)
    return _notification_output(
        item,
        include_sensitive_values=user_can_view_sensitive_values(user.role),
    )


@router.post("/read-all")
async def mark_all_read(user: CurrentUser, db: DbSession):
    await db.execute(
        update(Notification)
        .where(Notification.user_id == user.id, _visible_predicate(user), Notification.is_read.is_(False))
        .values(is_read=True, read_at=datetime.now(UTC))
    )
    await db.commit()
    return {"ok": True}

@router.get("/history", response_model=NotificationHistory)
async def notification_history(
    user: CurrentUser, db: DbSession,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=100),
    module: str | None = Query(default=None, max_length=40),
    action: str | None = Query(default=None, max_length=60),
    actor_id: int | None = Query(default=None, ge=1),
    work_order: str | None = Query(default=None, max_length=40),
    search: str | None = Query(default=None, max_length=120),
    date_from: date | None = Query(default=None),
    date_to: date | None = Query(default=None),
    unread_only: bool = Query(default=False),
):
    from fastapi import HTTPException
    if date_from and date_to and date_to < date_from:
        raise HTTPException(status_code=422, detail="Período inválido.")
    if module and not activity_visible(user.role, user.modules, module):
        raise HTTPException(status_code=403, detail="Módulo não autorizado para este perfil.")
    base = [Notification.user_id == user.id, _visible_predicate(user)]
    unread_count = int(await db.scalar(
        select(func.count(Notification.id)).where(*base, Notification.is_read.is_(False))
    ) or 0)
    conditions = list(base)
    if module:
        conditions.append(_EFFECTIVE_MODULE == module)
    if action:
        conditions.append(Notification.action == action)
    if actor_id is not None:
        conditions.append(Notification.actor_user_id == actor_id)
    if work_order:
        conditions.append(Notification.work_order_number.ilike(f"%{work_order.strip()}%"))
    if search and search.strip():
        q = f"%{search.strip()}%"
        conditions.append(or_(
            Notification.title.ilike(q), Notification.message.ilike(q),
            Notification.actor_name.ilike(q), Notification.equipment_name.ilike(q),
            Notification.work_order_number.ilike(q), Notification.details.ilike(q),
        ))
    # Datas informadas no painel referem-se ao calendário local da operação.
    local_zone = ZoneInfo("America/Recife")
    if date_from:
        start = datetime.combine(date_from, time.min, local_zone).astimezone(UTC)
        conditions.append(Notification.created_at >= start)
    if date_to:
        end = datetime.combine(date_to + timedelta(days=1), time.min, local_zone).astimezone(UTC)
        conditions.append(Notification.created_at < end)
    if unread_only:
        conditions.append(Notification.is_read.is_(False))
    total = int(await db.scalar(select(func.count(Notification.id)).where(*conditions)) or 0)
    items = list((await db.scalars(
        select(Notification).where(*conditions)
        .order_by(Notification.created_at.desc(), Notification.id.desc())
        .offset((page - 1) * page_size).limit(page_size)
    )).all())
    return NotificationHistory(
        items=[_notification_output(item, include_sensitive_values=user_can_view_sensitive_values(user.role)) for item in items],
        unread_count=unread_count, total=total, page=page, page_size=page_size,
    )


@router.get("/actors")
async def notification_actors(user: CurrentUser, db: DbSession):
    # IDs e nomes somente daqueles que já aparecem nas notificações autorizadas.
    rows = (await db.execute(
        select(Notification.actor_user_id, Notification.actor_name)
        .where(Notification.user_id == user.id, _visible_predicate(user),
               Notification.actor_user_id.is_not(None), Notification.actor_name.is_not(None))
        .distinct().order_by(Notification.actor_name).limit(300)
    )).all()
    return [{"id": uid, "name": name} for uid, name in rows]


# --- Inscrição opt-in em Web Push (mantém todas as notificações internas). ---
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError

from app.notifications.models import PushSubscription
from app.notifications.push import is_valid_push_endpoint, push_is_configured
from app.core.config import settings


class BrowserSubscriptionKeys(BaseModel):
    p256dh: str = Field(min_length=30, max_length=200, pattern=r"^[A-Za-z0-9_-]+={0,2}$")
    auth: str = Field(min_length=10, max_length=100, pattern=r"^[A-Za-z0-9_-]+={0,2}$")


class BrowserSubscription(BaseModel):
    endpoint: str = Field(max_length=1800)
    keys: BrowserSubscriptionKeys
    device_label: str | None = Field(default=None, max_length=100)


class BrowserUnsubscribe(BaseModel):
    endpoint: str = Field(max_length=1800)


@router.get("/push/config")
async def get_push_config(user: CurrentUser):
    return {
        "enabled": push_is_configured(),
        "public_key": settings.push_vapid_public_key if push_is_configured() else "",
    }


@router.post("/push/subscriptions", status_code=201)
async def add_push_subscription(data: BrowserSubscription, user: CurrentUser, db: DbSession):
    from fastapi import HTTPException

    if not push_is_configured():
        raise HTTPException(status_code=503, detail="Notificações push ainda não configuradas no servidor.")
    if not is_valid_push_endpoint(data.endpoint):
        raise HTTPException(status_code=422, detail="Serviço de push não reconhecido.")
    # Uma mesma inscrição de navegador nunca deve pertencer a dois usuários:
    # em dispositivos compartilhados, o último login autorizado assume o endpoint.
    entry = await db.scalar(
        select(PushSubscription).where(PushSubscription.endpoint == data.endpoint).with_for_update()
    )
    if entry:
        entry.user_id = user.id
        entry.p256dh = data.keys.p256dh
        entry.auth = data.keys.auth
        entry.device_label = data.device_label
    else:
        db.add(PushSubscription(
            user_id=user.id, endpoint=data.endpoint, p256dh=data.keys.p256dh,
            auth=data.keys.auth, device_label=data.device_label,
        ))
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="Inscrição registrada simultaneamente. Tente novamente.") from None
    return {"ok": True}


@router.post("/push/unsubscribe")
async def remove_push_subscription(data: BrowserUnsubscribe, user: CurrentUser, db: DbSession):
    from sqlalchemy import delete

    await db.execute(delete(PushSubscription).where(
        PushSubscription.user_id == user.id, PushSubscription.endpoint == data.endpoint,
    ))
    await db.commit()
    return {"ok": True}
