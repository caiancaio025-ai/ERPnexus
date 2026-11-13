from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest
from pydantic import TypeAdapter, ValidationError

from app.purchasing.schemas import PurchaseOutput


def _purchase(status: str, purchase_id: int = 1):
    return SimpleNamespace(
        id=purchase_id,
        code=f"PC-2026-{purchase_id:04d}",
        company_code="universo_eletronica",
        supplier_id=1,
        supplier_name="Fornecedor Teste",
        equipment_serial=None,
        invoice_number=None,
        client_destination=None,
        product_name="Produto",
        quantity=1,
        total_amount=Decimal("10.00"),
        origin="national",
        tracking_code=None,
        purchase_date=date(2026, 8, 25),
        estimated_delivery_date=date(2026, 8, 30),
        delivered_at=None,
        status=status,
        product_link=None,
        notes=None,
        attachment_name=None,
        attachment_mime=None,
        created_at=None,
        updated_at=None,
    )


def test_legacy_in_transit_is_normalized_in_output():
    item = TypeAdapter(PurchaseOutput).validate_python(
        _purchase("in_transit"), from_attributes=True
    )
    assert item.status == "shipped"


def test_orders_list_accepts_legacy_and_current_statuses():
    statuses = [
        "in_transit",
        "in_transit",
        "awaiting_payment",
        "ordered",
        "processing",
        "shipped",
        "customs",
        "delivered",
        "cancelled",
    ]
    items = TypeAdapter(list[PurchaseOutput]).validate_python(
        [_purchase(status, idx + 1) for idx, status in enumerate(statuses)],
        from_attributes=True,
    )
    assert [item.status for item in items[:2]] == ["shipped", "shipped"]
    assert [item.status for item in items[2:]] == statuses[2:]


def test_unknown_status_is_still_rejected():
    with pytest.raises(ValidationError):
        TypeAdapter(PurchaseOutput).validate_python(
            _purchase("broken_status"), from_attributes=True
        )
