from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.finance.service import build_finance_summary


class Rows:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows

    def one(self):
        assert len(self._rows) == 1
        return self._rows[0]


class FakeDB:
    def __init__(self):
        self.execute = AsyncMock(side_effect=[
            Rows([SimpleNamespace(
                opening_balance=Decimal("0.00"),
                settled_income_all=Decimal("100.00"),
                settled_expense_all=Decimal("50.00"),
            )]),
            Rows([SimpleNamespace(
                period_income=Decimal("1000.00"),
                period_expense=Decimal("400.00"),
                period_entry_count=3,
                period_income_count=2,
                period_expense_count=1,
                settled_income=Decimal("700.00"),
                settled_expense=Decimal("350.00"),
                pending_income=Decimal("300.00"),
                pending_expense=Decimal("50.00"),
                overdue_income=Decimal("275.00"),
                overdue_expense=Decimal("40.00"),
                overdue_count=2,
                due_soon_count=0,
            )]),
            Rows([]),
        ])
        self.scalars = AsyncMock(return_value=Rows([]))


@pytest.mark.asyncio
async def test_summary_exposes_overdue_amounts_independent_from_entry_page():
    db = FakeDB()
    summary = await build_finance_summary(
        db,
        company_code="universo_eletronica",
        consolidated=False,
        start_date=date(2026, 8, 1),
        end_date=date(2026, 8, 31),
        date_basis="posting",
    )

    assert summary.overdue_income == 275.0
    assert summary.overdue_expense == 40.0
    assert summary.overdue_count == 2
    assert summary.period_income == 1000.0
    assert summary.period_expense == 400.0
    assert summary.period_entry_count == 3
    assert summary.period_income_count == 2
    assert summary.period_expense_count == 1

    # Summary usa 4 round-trips: 2 agregações + eventos + fluxo.
    assert db.execute.await_count == 3
    assert db.scalars.await_count == 1
