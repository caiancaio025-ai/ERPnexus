from __future__ import annotations

from decimal import Decimal
from typing import Any, Iterable


PROTECTED_FIELDS = (
    "entry_type",
    "company_code",
    "work_order_id",
)

SHARED_FIELDS = (
    "invoice_type",
    "series",
    "nfse_number",
    "nfe_number",
    "counterparty_name",
    "description",
    "issue_date",
    "posting_date",
    "document_number",
)

INDIVIDUAL_FIELDS = (
    "amount",
    "due_date",
    "bank_name",
    "expense_kind",
    "account_id",
    "category_id",
    "payment_code",
    "notes",
)


def changed_fields(current: Any, incoming: Any, fields: Iterable[str]) -> list[str]:
    return [
        field
        for field in fields
        if getattr(current, field, None) != getattr(incoming, field, None)
    ]


def values_for(incoming: Any, fields: Iterable[str]) -> dict[str, Any]:
    return {field: getattr(incoming, field, None) for field in fields}


def apply_values(target: Any, values: dict[str, Any]) -> None:
    for field, value in values.items():
        setattr(target, field, value)


def total_from_installments(entries: Iterable[Any]) -> Decimal:
    return sum(
        (Decimal(str(getattr(entry, "amount"))) for entry in entries),
        start=Decimal("0.00"),
    )
