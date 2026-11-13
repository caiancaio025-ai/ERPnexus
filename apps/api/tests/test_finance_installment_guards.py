from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.finance.installment_edit import (
    INDIVIDUAL_FIELDS,
    PROTECTED_FIELDS,
    SHARED_FIELDS,
    apply_values,
    changed_fields,
    total_from_installments,
    values_for,
)
from app.finance.router import _block_grouped_entry_delete, _validate_grouped_installment_update
from app.finance.schemas import FinancialEntryUpdate


def grouped_entry() -> SimpleNamespace:
    return SimpleNamespace(
        id=10,
        obligation_id=5,
        installment_number=1,
        entry_type="expense",
        company_code="universo_eletronica",
        invoice_type=None,
        series=None,
        nfse_number=None,
        nfe_number=None,
        counterparty_name="Fornecedor",
        description="Compra parcelada",
        amount=Decimal("100.00"),
        issue_date=date(2026, 10, 1),
        posting_date=date(2026, 10, 1),
        due_date=date(2026, 10, 15),
        bank_name="Bradesco",
        expense_kind="supplier",
        account_id=None,
        category_id=None,
        document_number="DOC-1",
        payment_code="PIX-1",
        notes="Original",
        work_order_id=None,
    )


def update_payload(**changes) -> FinancialEntryUpdate:
    data = dict(
        entry_type="expense",
        company_code="universo_eletronica",
        invoice_type=None,
        series=None,
        nfse_number=None,
        nfe_number=None,
        counterparty_name="Fornecedor",
        description="Compra parcelada",
        amount=Decimal("125.00"),
        issue_date=date(2026, 10, 1),
        posting_date=date(2026, 10, 1),
        due_date=date(2026, 10, 20),
        bank_name="Itaú",
        expense_kind="tax",
        account_id=None,
        category_id=None,
        document_number="DOC-2",
        payment_code="PIX-2",
        notes="Corrigida",
        work_order_id=None,
        billing_confirmation=None,
    )
    data.update(changes)
    return FinancialEntryUpdate(**data)


def test_grouped_installment_accepts_individual_and_shared_corrections() -> None:
    entry = grouped_entry()
    payload = update_payload(
        counterparty_name="Fornecedor Corrigido",
        description="Compra corrigida",
        issue_date=date(2026, 10, 2),
        posting_date=date(2026, 10, 2),
    )

    _validate_grouped_installment_update(entry, payload)

    assert "amount" in INDIVIDUAL_FIELDS
    assert "due_date" in INDIVIDUAL_FIELDS
    assert "counterparty_name" in SHARED_FIELDS
    assert "description" in SHARED_FIELDS
    assert "posting_date" in SHARED_FIELDS


@pytest.mark.parametrize(
    "changes",
    [
        {"company_code": "solucoes_eletronica", "bank_name": "Bradesco"},
        {"entry_type": "income"},
        {"work_order_id": 999},
    ],
)
def test_grouped_installment_rejects_protected_changes(changes: dict) -> None:
    entry = grouped_entry()
    payload = update_payload(**changes)

    with pytest.raises(HTTPException) as exc:
        _validate_grouped_installment_update(entry, payload)

    assert exc.value.status_code == 409


def test_grouped_installment_delete_remains_blocked() -> None:
    with pytest.raises(HTTPException) as exc:
        _block_grouped_entry_delete(grouped_entry())

    assert exc.value.status_code == 409


def test_shared_fields_are_applied_to_all_siblings_and_total_is_recalculated() -> None:
    first = grouped_entry()
    second = grouped_entry()
    second.id = 11
    second.installment_number = 2
    second.amount = Decimal("200.00")

    payload = update_payload(
        counterparty_name="Fornecedor Novo",
        description="Obrigação atualizada",
        amount=Decimal("150.00"),
    )

    shared = values_for(payload, SHARED_FIELDS)
    individual = values_for(payload, INDIVIDUAL_FIELDS)

    for sibling in (first, second):
        apply_values(sibling, shared)
    apply_values(first, individual)

    assert first.counterparty_name == "Fornecedor Novo"
    assert second.counterparty_name == "Fornecedor Novo"
    assert first.description == second.description == "Obrigação atualizada"
    assert first.amount == Decimal("150.00")
    assert second.amount == Decimal("200.00")
    assert total_from_installments((first, second)) == Decimal("350.00")


def test_protected_field_contract_is_minimal_and_explicit() -> None:
    assert set(PROTECTED_FIELDS) == {"entry_type", "company_code", "work_order_id"}
    entry = grouped_entry()
    payload = update_payload()
    assert changed_fields(entry, payload, PROTECTED_FIELDS) == []
