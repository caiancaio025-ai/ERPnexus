"""Web Push opt-in; only deliver committed notifications for the owning user.

Each API worker polls the same PostgreSQL queue using SKIP LOCKED; no push
is sent before transaction commit. Notification delivery is best effort and
must never block business operations or break the in-app notification center.
"""
import asyncio
import json
import logging
from datetime import UTC, datetime
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.db import session_factory
from app.notifications.models import Notification, PushSubscription

logger = logging.getLogger(__name__)

# Web Push endpoints are external HTTP targets: restrict them to known push
# services to avoid using stored subscription endpoints for SSRF.
_PUSH_HOSTS = {
    "fcm.googleapis.com",
    "updates.push.services.mozilla.com",
    "push.services.mozilla.com",
    "web.push.apple.com",
}
_PUSH_SUFFIXES = (".notify.windows.com", ".push.apple.com")


def is_valid_push_endpoint(endpoint: str) -> bool:
    if not 30 <= len(endpoint) <= 1800:
        return False
    try:
        url = urlparse(endpoint)
        hostname = (url.hostname or "").lower()
        return (
            url.scheme == "https" and url.port in (None, 443)
            and bool(url.path) and not url.username and not url.password
            and not url.fragment
            and (hostname in _PUSH_HOSTS or any(hostname.endswith(s) for s in _PUSH_SUFFIXES))
        )
    except ValueError:
        return False


def _vapid_private_key_source() -> str:
    return settings.push_vapid_private_key_file or settings.push_vapid_private_key


def push_is_configured() -> bool:
    from pathlib import Path
    source = _vapid_private_key_source()
    file_is_readable = not settings.push_vapid_private_key_file or Path(source).is_file()
    return bool(settings.push_vapid_public_key and source and settings.push_vapid_subject and file_is_readable)


def safe_target(target: str | None) -> str:
    if not target or not target.startswith("/") or target.startswith("//") or "\\" in target:
        return "/painel?notificacoes=1"
    return target


def _send_one(sub: PushSubscription, payload: str) -> bool:
    """Runs on a worker thread. Return False for expired subscriptions."""
    from pywebpush import WebPushException, webpush

    try:
        webpush(
            subscription_info={
                "endpoint": sub.endpoint,
                "keys": {"p256dh": sub.p256dh, "auth": sub.auth},
            },
            data=payload,
            vapid_private_key=_vapid_private_key_source(),
            vapid_claims={"sub": settings.push_vapid_subject},
            ttl=3600,
            timeout=8,
        )
        return True
    except WebPushException as exc:
        status = getattr(getattr(exc, "response", None), "status_code", None)
        if status in (404, 410):
            return False
        logger.warning("Push não entregue (HTTP %s): %s", status, exc)
        return True
    except Exception:
        logger.exception("Falha não fatal ao enviar Web Push")
        return True


async def _deliver_pending(db: AsyncSession, *, limit: int = 15) -> int:
    rows = list((await db.scalars(
        select(Notification)
        .where(Notification.push_processed_at.is_(None))
        .order_by(Notification.id.asc())
        .with_for_update(skip_locked=True)
        .limit(limit)
    )).all())
    if not rows:
        return 0
    user_ids = {row.user_id for row in rows}
    subscriptions = list((await db.scalars(
        select(PushSubscription).where(PushSubscription.user_id.in_(user_ids))
    )).all())
    subs_by_user: dict[int, list[PushSubscription]] = {}
    for sub in subscriptions:
        subs_by_user.setdefault(sub.user_id, []).append(sub)

    invalid_sub_ids: set[int] = set()
    for notification in rows:
        # No amounts, customer details or message bodies on the lock screen.
        payload = json.dumps({
            "title": "SÊNTICO ERP · Nova atualização",
            "body": "Toque para consultar os detalhes no SÊNTICO.",
            "url": safe_target(notification.target),
            "tag": f"sentico-{notification.id}",
        }, ensure_ascii=False)
        for sub in subs_by_user.get(notification.user_id, []):
            if sub.id in invalid_sub_ids:
                continue
            valid = await asyncio.to_thread(_send_one, sub, payload)
            if not valid:
                invalid_sub_ids.add(sub.id)
        notification.push_processed_at = datetime.now(UTC)
    for sub in subscriptions:
        if sub.id in invalid_sub_ids:
            await db.delete(sub)
    await db.commit()
    return len(rows)


async def push_delivery_loop() -> None:
    """Polling in each worker is safe because PostgreSQL locks each row."""
    if not push_is_configured():
        logger.info("Web Push desabilitado: configure as três variáveis VAPID.")
        return
    logger.info("Web Push iniciado.")
    while True:
        try:
            async with session_factory() as db:
                processed = await _deliver_pending(db)
            await asyncio.sleep(2 if processed else 8)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Falha temporária no processamento Web Push")
            await asyncio.sleep(15)
