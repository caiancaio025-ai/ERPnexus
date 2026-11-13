from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from fastapi import Request
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import LoginAttempt
from app.auth.rate_limit import _client_ip, _hash_key
from app.core.config import settings

_TRACKING_SCOPE = "tracking_ip"


@dataclass(frozen=True, slots=True)
class TrackingRateLimitState:
    blocked: bool
    retry_after: int = 0


def _window_state(
    request_count: int,
    oldest_attempt: datetime | None,
    now: datetime,
) -> TrackingRateLimitState:
    if request_count < settings.tracking_rate_limit_ip_requests or oldest_attempt is None:
        return TrackingRateLimitState(blocked=False)

    expires_at = oldest_attempt + timedelta(seconds=settings.tracking_rate_limit_window_seconds)
    retry_after = max(1, int((expires_at - now).total_seconds() + 0.999))
    return TrackingRateLimitState(blocked=True, retry_after=retry_after)


async def tracking_rate_limit_state(
    db: AsyncSession,
    request: Request,
) -> TrackingRateLimitState:
    now = datetime.now(UTC)
    key_hash = _hash_key(_TRACKING_SCOPE, _client_ip(request))
    cutoff = now - timedelta(seconds=settings.tracking_rate_limit_window_seconds)

    row = (
        await db.execute(
            select(
                func.count(LoginAttempt.id),
                func.min(LoginAttempt.attempted_at),
            ).where(
                LoginAttempt.scope == _TRACKING_SCOPE,
                LoginAttempt.key_hash == key_hash,
                LoginAttempt.attempted_at > cutoff,
            )
        )
    ).one()

    state = _window_state(int(row[0] or 0), row[1], now)
    if state.blocked:
        return state

    db.add(
        LoginAttempt(
            scope=_TRACKING_SCOPE,
            key_hash=key_hash,
            attempted_at=now,
        )
    )

    retention_cutoff = now - timedelta(seconds=settings.tracking_rate_limit_retention_seconds)
    await db.execute(
        delete(LoginAttempt).where(
            LoginAttempt.scope == _TRACKING_SCOPE,
            LoginAttempt.attempted_at < retention_cutoff,
        )
    )
    await db.commit()

    return TrackingRateLimitState(blocked=False)
