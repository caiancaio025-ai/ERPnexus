from decimal import Decimal
from random import Random
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app.finance.billing_batches import allocate_installments, outgoing_invoice_number, outgoing_invoice_slot
from app.finance.idempotency import finance_request_fingerprint, fingerprint_mapping
from app.finance.schemas import FinancialBillingBatchInput, FinancialEntryInput


def batch_payload():
    return {
        "entry_type": "income", "company_code": "universo_eletronica", "nfse_number": "123",
        "counterparty_name": "Cliente teste", "description": "Manutenção em conjunto", "total_amount": "300.00",
        "issue_date": "2026-11-26", "posting_date": "2026-11-26", "bank_name": "Itaú",
        "work_orders": [{"work_order_id": 1, "version": 1, "amount": "100.00"}, {"work_order_id": 2, "version": 1, "amount": "200.00"}],
        "installments": [{"installment_number": i, "due_date": "2026-12-26", "amount": "100.00"} for i in range(1, 4)],
    }


@pytest.mark.parametrize("rows,columns", [
    (["100.00", "200.00"], ["100.00", "100.00", "100.00"]),
    (["0.01", "0.02"], ["0.03"]),
    (["0.02", "0.02"], ["0.02", "0.02"]),
    (["9.99", "0.02", "10.00"], ["0.03", "19.98"]),
    (["9999999999.99", "0.03"], ["3333333333.33", "3333333333.33", "3333333333.36"]),
])
def test_allocations_preserve_each_os_and_installment_to_the_cent(rows, columns):
    row_amounts, column_amounts = [Decimal(x) for x in rows], [Decimal(x) for x in columns]
    result = allocate_installments(row_amounts, column_amounts)
    assert [sum(row) for row in result] == row_amounts
    assert [sum(row[i] for row in result) for i in range(len(columns))] == column_amounts
    assert all(value > 0 and value.as_tuple().exponent == -2 for row in result for value in row)
    assert result == allocate_installments(row_amounts, column_amounts)


def test_many_unequal_cents_keep_both_independent_totals():
    random = Random(481126)
    for _ in range(100):
        n, m = random.randrange(1, 15), random.randrange(1, 15)
        source = [[random.randrange(1, 10000) for _ in range(m)] for _ in range(n)]
        rows = [Decimal(sum(row)) / 100 for row in source]
        columns = [Decimal(sum(row[i] for row in source)) / 100 for i in range(m)]
        actual = allocate_installments(rows, columns)
        assert [sum(row) for row in actual] == rows
        assert [sum(row[i] for row in actual) for i in range(m)] == columns
        assert all(value > 0 for row in actual for value in row)


@pytest.mark.parametrize("rows,columns", [
    (["0.01", "0.03"], ["0.02", "0.02"]),
    (["0.02", "0.02"], ["0.01", "0.03"]),
])
def test_impossible_positive_installments_are_rejected_explicitly(rows, columns):
    with pytest.raises(ValueError, match=r"pelo menos R\$ 0,01"):
        allocate_installments([Decimal(x) for x in rows], [Decimal(x) for x in columns])


@pytest.mark.parametrize("nfse,nfe,selected,expected", [
    ("123", None, None, "123"), (None, "456", None, "456"),
    ("123", "123", None, "123"), ("123", "456", " 456 ", "456"),
])
def test_outgoing_invoice_resolution_is_explicit(nfse, nfe, selected, expected):
    assert outgoing_invoice_number(SimpleNamespace(nfse_number=nfse, nfe_number=nfe, exit_invoice=selected)) == expected


def test_two_different_invoice_numbers_require_explicit_choice():
    with pytest.raises(HTTPException) as error:
        outgoing_invoice_number(SimpleNamespace(nfse_number="123", nfe_number="456", exit_invoice=None))
    assert error.value.status_code == 422


def test_outgoing_document_is_never_overwritten_or_duplicated():
    order = SimpleNamespace(number="OS-1", exit_invoice="111", exit_invoice_2="222", exit_invoice_3=None)
    assert outgoing_invoice_slot(order, "111") is None
    assert outgoing_invoice_slot(order, "222") is None
    assert outgoing_invoice_slot(order, "333") == "exit_invoice_3"
    order.exit_invoice_3 = "333"
    with pytest.raises(HTTPException) as error:
        outgoing_invoice_slot(order, "444")
    assert error.value.status_code == 409
    assert order.exit_invoice == "111" and order.exit_invoice_2 == "222"


@pytest.mark.parametrize("mutation,message", [
    (lambda data: data["work_orders"][1].update(work_order_id=1), "mesma OS"),
    (lambda data: data["work_orders"][0].update(amount="99.99"), "soma dos valores por OS"),
    (lambda data: data.update(work_order_id=1), "vínculo singular"),
])
def test_invalid_batch_contract_cannot_reach_database(mutation, message):
    data = batch_payload()
    mutation(data)
    with pytest.raises(ValidationError, match=message):
        FinancialBillingBatchInput.model_validate(data)


def test_optional_invoice_fields_preserve_historical_idempotency_fingerprint():
    data = batch_payload()
    data.pop("work_orders")  # Cliente antigo envia apenas o vínculo singular.
    data.update(amount="300.00", due_date="2026-12-26", work_order_id=1)
    payload = FinancialEntryInput.model_validate(data)
    legacy = payload.model_dump(mode="json", exclude={"exit_invoice", "work_order_version", "work_orders"})
    assert finance_request_fingerprint(payload) == fingerprint_mapping(legacy)
    changed = payload.model_copy(update={"exit_invoice": "321"})
    assert finance_request_fingerprint(changed) != finance_request_fingerprint(payload)
