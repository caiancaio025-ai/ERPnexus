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


@pytest.mark.asyncio
async def test_customer_overview_summary_uses_two_database_roundtrips():
    from app.customers.service import customer_overview_summary

    db = AsyncMock()

    aggregate_result = MagicMock()
    aggregate_result.one.return_value = SimpleNamespace(
        equipment_count=88,
        work_orders_count=88,
        quotes_count=68,
        quotes_total=251591.88,
    )

    recent_result = MagicMock()
    recent_result.mappings.return_value.all.return_value = [
        {
            "id": 1,
            "number": "30481",
            "equipment_id": 10,
            "equipment_serial": "SERIE-1",
            "status": "received",
            "priority": "normal",
            "opened_at": "2026-08-01",
            "quoted_value": None,
            "approved_value": None,
        }
    ]

    db.execute.side_effect = [aggregate_result, recent_result]

    summary = await customer_overview_summary(db, customer_id=541)

    assert summary.equipment_count == 88
    assert summary.work_orders_count == 88
    assert summary.quotes_count == 68
    assert summary.quotes_total == 251591.88
    assert len(summary.recent_work_orders) == 1
    assert summary.recent_work_orders[0]["number"] == "30481"
    assert db.execute.await_count == 2


@pytest.mark.asyncio
async def test_customer_overview_summary_handles_empty_customer_activity():
    from app.customers.service import customer_overview_summary

    db = AsyncMock()

    aggregate_result = MagicMock()
    aggregate_result.one.return_value = SimpleNamespace(
        equipment_count=0,
        work_orders_count=0,
        quotes_count=0,
        quotes_total=0,
    )

    recent_result = MagicMock()
    recent_result.mappings.return_value.all.return_value = []
    db.execute.side_effect = [aggregate_result, recent_result]

    summary = await customer_overview_summary(db, customer_id=999999)

    assert summary.equipment_count == 0
    assert summary.work_orders_count == 0
    assert summary.quotes_count == 0
    assert summary.quotes_total == 0.0
    assert summary.recent_work_orders == []
    assert db.execute.await_count == 2


def test_customer_detail_does_not_expose_legacy_heavy_collections():
    from app.customers.schemas import CustomerDetail

    legacy_fields = {"notes_history", "documents", "equipment", "work_orders", "quotes"}

    assert legacy_fields.isdisjoint(CustomerDetail.model_fields)
