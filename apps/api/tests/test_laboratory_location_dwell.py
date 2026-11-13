from datetime import UTC, datetime, timedelta

from app.laboratory.location_dwell import (
    LOCATION_DWELL_ATTENTION_SECONDS,
    LOCATION_DWELL_CRITICAL_SECONDS,
    location_dwell_level,
    location_dwell_seconds,
)


def test_location_dwell_threshold_boundaries() -> None:
    assert location_dwell_level(0) == "normal"
    assert location_dwell_level(LOCATION_DWELL_ATTENTION_SECONDS - 1) == "normal"
    assert location_dwell_level(LOCATION_DWELL_ATTENTION_SECONDS) == "attention"
    assert location_dwell_level(LOCATION_DWELL_CRITICAL_SECONDS - 1) == "attention"
    assert location_dwell_level(LOCATION_DWELL_CRITICAL_SECONDS) == "critical"


def test_location_dwell_seconds_uses_current_assignment_time() -> None:
    now = datetime(2026, 10, 13, 15, 0, tzinfo=UTC)
    assigned = now - timedelta(days=5, hours=3)
    assert location_dwell_seconds(assigned, now=now) == (5 * 24 + 3) * 3600


def test_location_dwell_seconds_never_negative() -> None:
    now = datetime(2026, 10, 13, 15, 0, tzinfo=UTC)
    assert location_dwell_seconds(now + timedelta(hours=1), now=now) == 0
