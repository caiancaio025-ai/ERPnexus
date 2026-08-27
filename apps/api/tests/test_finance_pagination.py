from datetime import UTC, date, datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from sqlalchemy.dialects import postgresql

from app.finance.models import FinancialEntry
from app.finance.router import list_entries


class ScalarRows:
    def __init__(self, rows):
        self._rows = rows

    def all(self):
        return self._rows


class FakeDB:
    def __init__(self, *, total: int, rows=None):
        self.scalar = AsyncMock(return_value=total)
        self.scalars = AsyncMock(return_value=ScalarRows(rows or []))


def make_entry(entry_id: int = 1) -> FinancialEntry:
    return FinancialEntry(
        id=entry_id,
        entry_type="income",
        company_code="universo_eletronica",
        nfse_number="100",
        counterparty_name="Cliente Teste",
        description="Parcela teste",
        amount=Decimal("500.00"),
        issue_date=date(2026, 8, 1),
        posting_date=date(2026, 8, 1),
        due_date=date(2026, 8, 20),
        bank_name="Itaú",
        status="pending",
        created_by=7,
        created_at=datetime(2026, 8, 1, tzinfo=UTC),
        updated_at=datetime(2026, 8, 1, tzinfo=UTC),
    )


def compile_sql(statement) -> str:
    return str(statement.compile(
        dialect=postgresql.dialect(),
        compile_kwargs={"literal_binds": True},
    ))


async def call_list(db: FakeDB, **overrides):
    params = {
        "company_code": None,
        "consolidated": False,
        "entry_type": "income",
        "entry_status": None,
        "overdue": False,
        "year": None,
        "month": None,
        "start_date": date(2026, 1, 1),
        "end_date": date(2026, 12, 31),
        "date_basis": "posting",
        "search": None,
        "page": 1,
        "page_size": 50,
        "_": SimpleNamespace(id=7),
        "db": db,
    }
    params.update(overrides)
    return await list_entries(**params)


@pytest.mark.asyncio
async def test_entries_are_paginated_and_report_total():
    db = FakeDB(total=101, rows=[make_entry(51)])

    result = await call_list(db, page=2)

    assert result.page == 2
    assert result.page_size == 50
    assert result.total == 101
    assert result.pages == 3
    assert [item.id for item in result.items] == [51]

    data_sql = compile_sql(db.scalars.await_args.args[0])
    assert "LIMIT 50 OFFSET 50" in data_sql


@pytest.mark.asyncio
async def test_page_is_clamped_after_filters_or_deletion():
    db = FakeDB(total=101, rows=[make_entry(101)])

    result = await call_list(db, page=9)

    assert result.page == 3
    assert result.pages == 3
    data_sql = compile_sql(db.scalars.await_args.args[0])
    assert "LIMIT 50 OFFSET 100" in data_sql


@pytest.mark.asyncio
async def test_overdue_and_work_order_search_are_server_side():
    db = FakeDB(total=1, rows=[make_entry()])

    await call_list(db, overdue=True, search="OS-123")

    count_sql = compile_sql(db.scalar.await_args.args[0])
    assert "financial_entries.status = 'pending'" in count_sql
    assert "financial_entries.due_date <" in count_sql
    assert "laboratory_work_orders.number ILIKE '%%OS-123%%'" in count_sql
    assert "financial_entries.work_order_id IN" in count_sql


@pytest.mark.asyncio
async def test_overdue_rejects_incompatible_settled_status():
    db = FakeDB(total=0)

    with pytest.raises(HTTPException) as exc:
        await call_list(db, overdue=True, entry_status="received")

    assert exc.value.status_code == 422
    db.scalar.assert_not_awaited()
    db.scalars.assert_not_awaited()
