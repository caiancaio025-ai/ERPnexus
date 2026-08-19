import hashlib
import math
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from fastapi import Request
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import LoginAttempt
from app.core.config import settings

_IDENTIFIER_SCOPE = "identifier"
_IP_SCOPE = "ip"


@dataclass(frozen=True, slots=True)
class RateLimitState:
    blocked: bool
    retry_after: int = 0


def _hash_key(scope: str, value: str) -> str:
    normalized = value.strip().lower()
    payload = f"{scope}:{normalized}".encode()
    return hashlib.sha256(payload).hexdigest()


def _client_ip(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        candidates = [part.strip() for part in forwarded_for.split(",") if part.strip()]
        if candidates:
            return candidates[-1]

    if request.client:
        return request.client.host

    return "unknown"


def _rate_limit_keys(request: Request, identifier: str) -> tuple[tuple[str, str, int], ...]:
    return (
        (
            _IDENTIFIER_SCOPE,
            _hash_key(_IDENTIFIER_SCOPE, identifier),
            settings.login_rate_limit_identifier_failures,
        ),
        (
            _IP_SCOPE,
            _hash_key(_IP_SCOPE, _client_ip(request)),
            settings.login_rate_limit_ip_failures,
        ),
    )


async def _scope_state(
    db: AsyncSession,
    *,
    scope: str,
    key_hash: str,
    limit: int,
    now: datetime,
) -> RateLimitState:
    cutoff = now - timedelta(seconds=settings.login_rate_limit_window_seconds)
    row = (
        await db.execute(
            select(
                func.count(LoginAttempt.id),
                func.min(LoginAttempt.attempted_at),
            ).where(
                LoginAttempt.scope == scope,
                LoginAttempt.key_hash == key_hash,
                LoginAttempt.attempted_at > cutoff,
            )
        )
    ).one()

    failures = int(row[0] or 0)
    oldest_attempt = row[1]
    if failures < limit or oldest_attempt is None:
        return RateLimitState(blocked=False)

    expires_at = oldest_attempt + timedelta(
        seconds=settings.login_rate_limit_window_seconds
    )
    retry_after = max(1, math.ceil((expires_at - now).total_seconds()))
    return RateLimitState(blocked=True, retry_after=retry_after)


async def login_rate_limit_state(
    db: AsyncSession,
    request: Request,
    identifier: str,
) -> RateLimitState:
    now = datetime.now(UTC)
    retry_after = 0

    for scope, key_hash, limit in _rate_limit_keys(request, identifier):
        state = await _scope_state(
            db,
            scope=scope,
            key_hash=key_hash,
            limit=limit,
            now=now,
        )
        if state.blocked:
            retry_after = max(retry_after, state.retry_after)

    return RateLimitState(
        blocked=retry_after > 0,
        retry_after=retry_after,
    )


async def record_failed_login(
    db: AsyncSession,
    request: Request,
    identifier: str,
) -> RateLimitState:
    now = datetime.now(UTC)

    for scope, key_hash, _limit in _rate_limit_keys(request, identifier):
        db.add(
            LoginAttempt(
                scope=scope,
                key_hash=key_hash,
                attempted_at=now,
            )
        )

    retention_cutoff = now - timedelta(
        seconds=settings.login_rate_limit_retention_seconds
    )
    await db.execute(
        delete(LoginAttempt).where(LoginAttempt.attempted_at < retention_cutoff)
    )
    await db.commit()

    return await login_rate_limit_state(db, request, identifier)


async def clear_identifier_failures(db: AsyncSession, identifier: str) -> None:
    await db.execute(
        delete(LoginAttempt).where(
            LoginAttempt.scope == _IDENTIFIER_SCOPE,
            LoginAttempt.key_hash == _hash_key(_IDENTIFIER_SCOPE, identifier),
        )
    )
