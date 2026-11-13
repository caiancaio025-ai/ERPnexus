from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.finance.installment_edit import (
    INDIVIDUAL_FIELDS,
    SHARED_FIELDS,
    apply_values,
    total_from_installments,
    values_for,
)
from app.finance.router import _block_grouped_entry_delete, _validate_grouped_installment_update
from app.finance.schemas import FinancialEntryUpdate


def _entry(entry_id: int = 10, installment: int = 1, amount: str = "100.00"):
    return SimpleNamespace(
        id=entry_id,
        obligation_id=5,
        installment_number=installment,
        entry_type="expense",
        company_code="universo_eletronica",
        invoice_type=None,
        series=None,
        nfse_number=None,
        nfe_number=None,
        counterparty_name="Fornecedor Teste",
        description="Compra parcelada",
        amount=Decimal(amount),
        issue_date=date(2026, 10, 8),
        posting_date=date(2026, 10, 8),
        due_date=date(2026, 10, 20),
        bank_name="Bradesco",
        expense_kind="supplier",
        account_id=None,
        category_id=None,
        document_number="DOC-1",
        payment_code="PIX-OLD",
        notes="Parcela original",
        work_order_id=None,
    )


def _payload(**changes):
    data = dict(
        entry_type="expense",
        company_code="universo_eletronica",
        invoice_type=None,
        series=None,
        nfse_number=None,
        nfe_number=None,
        counterparty_name="Fornecedor Corrigido",
        description="Compra corrigida",
        amount=Decimal("125.50"),
        issue_date=date(2026, 10, 9),
        posting_date=date(2026, 10, 9),
        due_date=date(2026, 10, 25),
        bank_name="Itaú",
        expense_kind="tax",
        account_id=None,
        category_id=None,
        document_number="DOC-1-A",
        payment_code="PIX-NEW",
        notes="Parcela corrigida",
        work_order_id=None,
        billing_confirmation=None,
    )
    data.update(changes)
    return FinancialEntryUpdate(**data)


def test_grouped_installment_allows_operational_and_shared_corrections() -> None:
    entry = _entry()
    payload = _payload()
    _validate_grouped_installment_update(entry, payload)

    assert {"amount", "due_date", "bank_name", "payment_code", "notes"} <= set(INDIVIDUAL_FIELDS)
    assert {"counterparty_name", "description", "issue_date", "posting_date", "document_number"} <= set(SHARED_FIELDS)


@pytest.mark.parametrize(
    "changes",
    [
        {"company_code": "solucoes_eletronica", "bank_name": "Bradesco"},
        {"entry_type": "income"},
        {"work_order_id": 42},
    ],
)
def test_grouped_installment_rejects_structural_changes(changes: dict) -> None:
    entry = _entry()
    payload = _payload(**changes)
    with pytest.raises(HTTPException) as exc:
        _validate_grouped_installment_update(entry, payload)
    assert exc.value.status_code == 409


def test_grouped_installment_still_cannot_be_deleted() -> None:
    with pytest.raises(HTTPException) as exc:
        _block_grouped_entry_delete(_entry())
    assert exc.value.status_code == 409


def test_editing_one_installment_keeps_shared_data_consistent() -> None:
    first = _entry(10, 1, "100.00")
    second = _entry(11, 2, "200.00")
    payload = _payload(amount=Decimal("150.00"))

    shared = values_for(payload, SHARED_FIELDS)
    individual = values_for(payload, INDIVIDUAL_FIELDS)
    for item in (first, second):
        apply_values(item, shared)
    apply_values(first, individual)

    assert first.counterparty_name == second.counterparty_name == "Fornecedor Corrigido"
    assert first.issue_date == second.issue_date == date(2026, 10, 9)
    assert first.amount == Decimal("150.00")
    assert second.amount == Decimal("200.00")
    assert total_from_installments((first, second)) == Decimal("350.00")
