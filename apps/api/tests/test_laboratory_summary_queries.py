from decimal import Decimal
from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.laboratory.service import work_order_period_range, work_order_summary_counts


class _OneRowResult:
    def __init__(self, row):
        self._row = row

    def one(self):
        return self._row


@pytest.mark.asyncio
async def test_work_order_summary_counts_uses_one_aggregate_query_and_preserves_values():
    row = SimpleNamespace(
        total_open=21,
        analyzed=2,
        awaiting_approval=3,
        approved=4,
        awaiting_analysis=5,
        in_repair=6,
        in_testing=7,
        high_priority=8,
        completed_month=9,
        approved_total=Decimal("12500.50"),
        awaiting_approval_total=Decimal("8300.25"),
    )
    db = SimpleNamespace(execute=AsyncMock(return_value=_OneRowResult(row)))

    summary = await work_order_summary_counts(
        db,
        company_code="universo_eletronica",
        opened_from=date(2026, 8, 1),
        opened_before=date(2026, 9, 1),
        completed_from=date(2026, 8, 1),
    )

    assert summary == {
        "total_open": 21,
        "analyzed": 2,
        "awaiting_approval": 3,
        "approved": 4,
        "awaiting_analysis": 5,
        "in_repair": 6,
        "in_testing": 7,
        "high_priority": 8,
        "completed_month": 9,
        "approved_total": Decimal("12500.50"),
        "awaiting_approval_total": Decimal("8300.25"),
    }
    db.execute.assert_awaited_once()

    statement = db.execute.await_args.args[0]
    sql = str(statement.compile(compile_kwargs={"literal_binds": True}))
    assert "FILTER (WHERE" in sql
    assert "laboratory_work_orders.company_code = 'universo_eletronica'" in sql
    assert "laboratory_work_orders.opened_at >= '2026-08-01'" in sql
    assert "laboratory_work_orders.opened_at < '2026-09-01'" in sql
    assert "laboratory_work_orders.completed_at >= '2026-08-01'" in sql
    assert "laboratory_work_orders.status IN ('received', 'awaiting_analysis')" in sql
    assert "laboratory_work_orders.priority IN ('high', 'urgent')" in sql


@pytest.mark.asyncio
async def test_work_order_summary_counts_converts_null_aggregates_to_zero():
    row = SimpleNamespace(
        total_open=None,
        analyzed=None,
        awaiting_approval=None,
        approved=None,
        awaiting_analysis=None,
        in_repair=None,
        in_testing=None,
        high_priority=None,
        completed_month=None,
        approved_total=None,
        awaiting_approval_total=None,
    )
    db = SimpleNamespace(execute=AsyncMock(return_value=_OneRowResult(row)))

    summary = await work_order_summary_counts(
        db,
        completed_from=date(2026, 8, 1),
    )

    assert set(summary.values()) == {0}
    db.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_work_order_period_range_combines_min_and_max_in_one_query():
    row = SimpleNamespace(latest=date(2026, 8, 27), earliest=date(2024, 1, 5))
    db = SimpleNamespace(execute=AsyncMock(return_value=_OneRowResult(row)))

    latest, earliest = await work_order_period_range(
        db,
        company_code="universo_automacao",
    )

    assert latest == date(2026, 8, 27)
    assert earliest == date(2024, 1, 5)
    db.execute.assert_awaited_once()

    statement = db.execute.await_args.args[0]
    sql = str(statement.compile(compile_kwargs={"literal_binds": True}))
    assert "max(laboratory_work_orders.opened_at)" in sql
    assert "min(laboratory_work_orders.opened_at)" in sql
    assert "laboratory_work_orders.company_code = 'universo_automacao'" in sql
