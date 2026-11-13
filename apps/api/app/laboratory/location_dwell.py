from __future__ import annotations

from datetime import UTC, datetime

LOCATION_DWELL_ATTENTION_DAYS = 4
LOCATION_DWELL_CRITICAL_DAYS = 8

SECONDS_PER_DAY = 24 * 60 * 60
LOCATION_DWELL_ATTENTION_SECONDS = LOCATION_DWELL_ATTENTION_DAYS * SECONDS_PER_DAY
LOCATION_DWELL_CRITICAL_SECONDS = LOCATION_DWELL_CRITICAL_DAYS * SECONDS_PER_DAY


def location_dwell_level(duration_seconds: int) -> str:
    duration = max(0, int(duration_seconds))
    if duration >= LOCATION_DWELL_CRITICAL_SECONDS:
        return "critical"
    if duration >= LOCATION_DWELL_ATTENTION_SECONDS:
        return "attention"
    return "normal"


def location_dwell_seconds(
    assigned_at: datetime | None,
    *,
    now: datetime | None = None,
) -> int:
    if assigned_at is None:
        return 0

    current = now or datetime.now(UTC)
    start = assigned_at
    if start.tzinfo is None:
        start = start.replace(tzinfo=UTC)
    if current.tzinfo is None:
        current = current.replace(tzinfo=UTC)

    return max(0, int((current - start).total_seconds()))
