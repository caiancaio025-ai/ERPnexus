from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest

from app.finance.service import build_finance_summary


class Rows:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class FakeDB:
    def __init__(self):
        self.scalar = AsyncMock(side_effect=[
            Decimal("0.00"),
            Decimal("100.00"),
            Decimal("50.00"),
            0,
        ])
        self.execute = AsyncMock(side_effect=[
            Rows([("income", Decimal("1000.00"), 2), ("expense", Decimal("400.00"), 1)]),
            Rows([("income", Decimal("700.00")), ("expense", Decimal("350.00"))]),
            Rows([("income", Decimal("300.00")), ("expense", Decimal("50.00"))]),
            Rows([("income", Decimal("275.00"), 1), ("expense", Decimal("40.00"), 1)]),
            Rows([]),
        ])
        self.scalars = AsyncMock(return_value=Rows([]))


@pytest.mark.asyncio
async def test_summary_exposes_overdue_amounts_independent_from_entry_page():
    summary = await build_finance_summary(
        FakeDB(),
        company_code="universo_eletronica",
        consolidated=False,
        start_date=date(2026, 8, 1),
        end_date=date(2026, 8, 31),
        date_basis="posting",
    )

    assert summary.overdue_income == 275.0
    assert summary.overdue_expense == 40.0
    assert summary.overdue_count == 2
