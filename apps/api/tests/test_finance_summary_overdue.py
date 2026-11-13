from datetime import date, timedelta
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
            Rows([]),  # fluxo semanal do período
            Rows([]),  # pendências por vencimento (forecast + aging + 13 semanas)
            Rows([]),  # série mensal/anual
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
    assert summary.current_balance == 50.0
    assert summary.projected_balance == 50.0
    assert len(summary.weekly_forecast_13w) == 13
    assert summary.weekly_forecast_13w[0].opening_balance == 50.0
    assert summary.weekly_forecast_13w[-1].closing_balance == 50.0
    assert len(summary.aging) == 8
    assert len(summary.monthly_flow) == 12

    # Sem pendências, não há round-trip adicional para reconhecimentos de alertas.
    assert db.execute.await_count == 5
    assert db.scalars.await_count == 1

@pytest.mark.asyncio
async def test_summary_builds_13_week_forecast_aging_and_global_projection():
    today = date.today()
    db = FakeDB()
    db.execute = AsyncMock(side_effect=[
        Rows([SimpleNamespace(
            opening_balance=Decimal("1000.00"),
            settled_income_all=Decimal("500.00"),
            settled_expense_all=Decimal("200.00"),
        )]),
        Rows([SimpleNamespace(
            period_income=Decimal("0.00"),
            period_expense=Decimal("0.00"),
            period_entry_count=0,
            period_income_count=0,
            period_expense_count=0,
            settled_income=Decimal("0.00"),
            settled_expense=Decimal("0.00"),
            pending_income=Decimal("0.00"),
            pending_expense=Decimal("0.00"),
            overdue_income=Decimal("0.00"),
            overdue_expense=Decimal("0.00"),
            overdue_count=0,
            due_soon_count=0,
        )]),
        Rows([]),
        Rows([
            (1, today - timedelta(days=100), "income", "Cliente antigo", "Receita vencida", Decimal("100.00"), "universo_eletronica", "Bradesco"),
            (2, today - timedelta(days=10), "expense", "Fornecedor vencido", "Despesa vencida", Decimal("50.00"), "universo_eletronica", "Itaú"),
            (3, today, "income", "Cliente hoje", "Receita hoje", Decimal("25.00"), "universo_eletronica", "Bradesco"),
            (4, today + timedelta(days=3), "expense", "Fornecedor próximo", "Despesa próxima", Decimal("20.00"), "universo_eletronica", "Itaú"),
            (5, today + timedelta(days=10), "income", "Cliente futuro", "Receita futura", Decimal("200.00"), "universo_eletronica", "Bradesco"),
            (6, today + timedelta(days=40), "expense", "Fornecedor futuro", "Despesa futura", Decimal("300.00"), "universo_eletronica", "Itaú"),
            (7, today + timedelta(days=100), "income", "Cliente distante", "Receita distante", Decimal("400.00"), "universo_eletronica", "Bradesco"),
        ]),
        Rows([]),  # reconhecimentos de alertas
        Rows([
            (
                today.month,
                Decimal("900.00"),
                Decimal("400.00"),
                Decimal("600.00"),
                Decimal("250.00"),
                Decimal("300.00"),
                Decimal("150.00"),
            ),
        ]),
    ])

    summary = await build_finance_summary(
        db,
        company_code="universo_eletronica",
        consolidated=False,
        start_date=date(today.year, 1, 1),
        end_date=date(today.year, 12, 31),
        date_basis="posting",
    )

    assert summary.current_balance == 1300.0
    assert summary.projected_balance == 1655.0
    assert len(summary.weekly_forecast_13w) == 13
    first_week = summary.weekly_forecast_13w[0]
    assert first_week.opening_balance == 1300.0
    assert first_week.overdue_income == 100.0
    assert first_week.overdue_expense == 50.0
    assert first_week.income == 25.0
    assert first_week.expense == 20.0
    assert first_week.closing_balance == 1355.0

    urgent_by_id = {event.id: event for event in summary.urgent_events}
    assert urgent_by_id[1].status == "overdue"
    assert urgent_by_id[2].status == "overdue"
    assert urgent_by_id[3].status == "due_soon"
    assert urgent_by_id[4].status == "due_soon"
    assert 5 not in urgent_by_id

    forecast_today = next(point for point in summary.forecast_flow if point.date == today)
    assert forecast_today.items[0].counterparty_name == "Cliente hoje"
    assert forecast_today.items[0].amount == 25.0

    aging = {bucket.key: bucket for bucket in summary.aging}
    assert aging["overdue_90_plus"].income == 100.0
    assert aging["overdue_1_30"].expense == 50.0
    assert aging["due_today"].income == 25.0
    assert aging["due_1_7"].expense == 20.0
    assert aging["due_8_30"].income == 200.0
    assert aging["due_31_plus"].income == 400.0
    assert aging["due_31_plus"].expense == 300.0

    month = summary.monthly_flow[today.month - 1]
    assert month.income == 900.0
    assert month.expense == 400.0
    assert month.result == 500.0
