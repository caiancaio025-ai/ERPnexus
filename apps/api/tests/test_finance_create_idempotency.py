from datetime import date
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.finance.idempotency import finance_request_fingerprint
from app.finance.models import FinancialEntry
from app.finance.router import create_entry
from app.finance.schemas import FinancialEntryInput


class FakeDB:
    def __init__(self):
        self.scalar = AsyncMock(return_value=None)
        self.flush = AsyncMock()
        self.commit = AsyncMock()
        self.refresh = AsyncMock()
        self.rollback = AsyncMock()
        self.add = MagicMock()


def make_payload(*, due_date: date, work_order_id: int = 123) -> FinancialEntryInput:
    return FinancialEntryInput(
        entry_type="income",
        company_code="universo_eletronica",
        nfse_number="100",
        counterparty_name="Cliente Teste",
        description="Parcela da NF 100",
        amount=Decimal("500.00"),
        issue_date=date(2026, 9, 1),
        posting_date=date(2026, 9, 1),
        due_date=due_date,
        bank_name="Itaú",
        work_order_id=work_order_id,
    )


@pytest.mark.asyncio
async def test_same_work_order_accepts_multiple_installments(monkeypatch):
    order = SimpleNamespace(id=123, number="OS-123", company_code="universo_eletronica")
    monkeypatch.setattr("app.finance.router._work_order_or_404", AsyncMock(return_value=order))
    monkeypatch.setattr("app.finance.router._validate_billing_confirmation", AsyncMock(return_value={"status": "complete"}))
    mark_invoiced = AsyncMock()
    monkeypatch.setattr("app.finance.router._mark_work_order_invoiced", mark_invoiced)

    first_db = FakeDB()
    second_db = FakeDB()
    user = SimpleNamespace(id=7)

    first = await create_entry(make_payload(due_date=date(2026, 9, 10)), user, first_db, "req-1")
    second = await create_entry(make_payload(due_date=date(2026, 10, 10)), user, second_db, "req-2")

    assert first.work_order_id == 123
    assert second.work_order_id == 123
    assert first.nfse_number == second.nfse_number == "100"
    assert first.due_date != second.due_date
    assert first_db.commit.await_count == 1
    assert second_db.commit.await_count == 1
    assert mark_invoiced.await_count == 2


@pytest.mark.asyncio
async def test_repeated_same_idempotency_key_returns_existing_entry(monkeypatch):
    payload = make_payload(due_date=date(2026, 9, 10))
    existing = FinancialEntry(
        id=999,
        entry_type="income",
        company_code="universo_eletronica",
        nfse_number="100",
        counterparty_name="Cliente Teste",
        description="Parcela da NF 100",
        amount=Decimal("500.00"),
        issue_date=date(2026, 9, 1),
        posting_date=date(2026, 9, 1),
        due_date=date(2026, 9, 10),
        bank_name="Itaú",
        status="pending",
        created_by=7,
        idempotency_key="same-request",
        idempotency_fingerprint=finance_request_fingerprint(payload),
    )
    db = FakeDB()
    db.scalar.return_value = existing

    result = await create_entry(payload, SimpleNamespace(id=7), db, "same-request")

    assert result is existing
    db.add.assert_not_called()
    db.flush.assert_not_awaited()
    db.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_same_idempotency_key_with_different_payload_is_rejected():
    original = make_payload(due_date=date(2026, 9, 10))
    changed = make_payload(due_date=date(2026, 10, 10))
    existing = FinancialEntry(
        id=999,
        entry_type="income",
        company_code="universo_eletronica",
        nfse_number="100",
        counterparty_name="Cliente Teste",
        description="Parcela da NF 100",
        amount=Decimal("500.00"),
        issue_date=date(2026, 9, 1),
        posting_date=date(2026, 9, 1),
        due_date=date(2026, 9, 10),
        bank_name="Itaú",
        status="pending",
        created_by=7,
        idempotency_key="same-request",
        idempotency_fingerprint=finance_request_fingerprint(original),
    )
    db = FakeDB()
    db.scalar.return_value = existing

    with pytest.raises(HTTPException) as exc:
        await create_entry(changed, SimpleNamespace(id=7), db, "same-request")

    assert exc.value.status_code == 409
    assert "dados diferentes" in exc.value.detail
