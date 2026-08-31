from datetime import UTC, datetime, timedelta

from app.core.config import settings
from app.tracking.rate_limit import _window_state


def test_tracking_window_allows_requests_below_limit() -> None:
    now = datetime(2026, 8, 31, 12, 0, tzinfo=UTC)
    state = _window_state(
        settings.tracking_rate_limit_ip_requests - 1,
        now - timedelta(seconds=10),
        now,
    )

    assert state.blocked is False
    assert state.retry_after == 0


def test_tracking_window_blocks_at_limit_with_retry_after() -> None:
    now = datetime(2026, 8, 31, 12, 0, tzinfo=UTC)
    oldest = now - timedelta(seconds=15)
    state = _window_state(settings.tracking_rate_limit_ip_requests, oldest, now)

    assert state.blocked is True
    assert state.retry_after == settings.tracking_rate_limit_window_seconds - 15
