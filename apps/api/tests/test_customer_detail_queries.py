from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.customers.service import customer_activity_counts


@pytest.mark.asyncio
async def test_customer_activity_counts_uses_single_database_roundtrip():
    db = AsyncMock()

    result = MagicMock()
    result.one.return_value = SimpleNamespace(
        work_orders_count=88,
        quotes_count=68,
    )
    db.execute.return_value = result

    counts = await customer_activity_counts(
        db,
        customer_id=541,
    )

    assert counts == (88, 68)
    db.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_customer_activity_counts_handles_zero_values():
    db = AsyncMock()

    result = MagicMock()
    result.one.return_value = SimpleNamespace(
        work_orders_count=0,
        quotes_count=0,
    )
    db.execute.return_value = result

    counts = await customer_activity_counts(
        db,
        customer_id=999999,
    )

    assert counts == (0, 0)
    db.execute.assert_awaited_once()
