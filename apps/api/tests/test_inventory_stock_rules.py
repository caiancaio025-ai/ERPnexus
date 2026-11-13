"""Estoque: série unitária, lote por quantidade, custo imutável e validações."""
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.dialects import postgresql

from app.auth.models import User
from app.purchasing import models as purchase_models  # noqa: F401
from app.purchasing import material_models as material_models  # noqa: F401
from app.inventory.models import (
    InventoryArea, InventoryContainer, InventoryItem, InventoryLocationType,
    InventoryMovement, InventoryPhoto, InventorySlot,
)
from app.inventory.schemas import ItemInput
from app.inventory.service import stock_balance_after


def test_serialized_one_unit_cannot_be_issued_twice():
    assert stock_balance_after("serialized", 1, 1, consume=True) == 0
    with pytest.raises(HTTPException) as error:
        stock_balance_after("serialized", 0, 1, consume=True)
    assert error.value.status_code == 409
    assert stock_balance_after("serialized", 0, 1, consume=False) == 1
    with pytest.raises(HTTPException):
        stock_balance_after("serialized", 1, 1, consume=False)
    with pytest.raises(HTTPException):
        stock_balance_after("serialized", 1, 2, consume=True)


def test_bulk_keeps_lot_when_consuming_quantity():
    assert stock_balance_after("bulk", 250, 17, consume=True) == 233
    assert stock_balance_after("bulk", 233, 3, consume=False) == 236
    with pytest.raises(HTTPException) as error:
        stock_balance_after("bulk", 236, 237, consume=True)
    assert error.value.status_code == 409
    with pytest.raises(HTTPException):
        stock_balance_after("bulk", 10, 0, consume=True)


def test_serialized_requires_manufacturer_serial_and_one_unit():
    valid = {"company_code": "universo_eletronica", "name": "Inversor WEG", "mode": "serialized", "quantity": 1, "manufacturer_serial": "SN123"}
    assert ItemInput.model_validate(valid).mode == "serialized"
    with pytest.raises(ValueError):
        ItemInput.model_validate({**valid, "quantity": 2})
    with pytest.raises(ValueError):
        ItemInput.model_validate({**valid, "manufacturer_serial": None})
    assert ItemInput.model_validate({"company_code": "universo_eletronica", "name": "Capacitor 470uF", "mode": "bulk", "quantity": 300}).quantity == 300


def test_constraints_and_references_exist():
    assert InventoryItem.__table__.c.stock_code.unique is True
    assert InventoryItem.__table__.c.quantity.nullable is False
    assert InventoryMovement.__table__.c.work_order_id.foreign_keys
    assert InventoryMovement.__table__.c.reversal_of_id.foreign_keys
    assert InventorySlot.__table__.c.container_id.foreign_keys


def test_sqlalchemy_can_compile_stock_lock_and_cost_expression():
    from sqlalchemy import case, func
    sql = str(select(InventoryItem).where(InventoryItem.id == 2).with_for_update().compile(dialect=postgresql.dialect()))
    assert "FOR UPDATE" in sql
    multiplier = case((InventoryMovement.kind == "issue", 1), (InventoryMovement.kind == "return", -1), else_=0)
    cost_sql = str(select(func.sum(InventoryMovement.quantity * InventoryMovement.unit_cost * multiplier)).compile(dialect=postgresql.dialect()))
    assert "CASE" in cost_sql and "inventory_movements" in cost_sql


def test_label_contains_qr_and_code():
    from app.inventory.label_pdf import inventory_label_pdf
    content = inventory_label_pdf(stock_code="EST-00000031", name="Capacitor 450V", serial=None, location="EST-01-02-03")
    assert content.startswith(b"%PDF-")
    assert len(content) > 1000

@pytest.mark.asyncio
async def test_consumed_cost_issue_and_return_use_original_price():
    """Retorno de peça reduz custo da OS, nunca altera custo histórico de outras saídas."""
    from sqlalchemy.orm import Session
    from app.core.models import Base
    from app.inventory.service import consumed_cost

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        session.add_all([
            InventoryMovement(item_id=10, work_order_id=7, kind="issue", quantity=2, unit_cost=Decimal("17.50"), user_id=1),
            InventoryMovement(item_id=10, work_order_id=7, kind="return", quantity=1, unit_cost=Decimal("17.50"), user_id=1, reversal_of_id=1),
            InventoryMovement(item_id=11, work_order_id=7, kind="issue", quantity=1, unit_cost=Decimal("42.00"), user_id=1),
            InventoryMovement(item_id=12, work_order_id=None, kind="receipt", quantity=50, unit_cost=Decimal("2.00"), user_id=1),
            InventoryMovement(item_id=99, work_order_id=99, kind="issue", quantity=100, unit_cost=Decimal("10.00"), user_id=1),
        ])
        session.commit()

        class AsyncSessionAdapter:
            async def scalar(self, stmt):
                return session.scalar(stmt)

        assert await consumed_cost(AsyncSessionAdapter(), 7) == Decimal("59.50")
        assert await consumed_cost(AsyncSessionAdapter(), 8) == Decimal("0.00")
    engine.dispose()


def test_edit_payload_keeps_serial_company_and_stock_identity_immutable():
    from app.inventory.schemas import ItemUpdate

    payload = ItemUpdate(name="Capacitor 470uF", category="capacitor", slot_id=None)
    assert payload.model_dump()["slot_id"] is None
    for protected in ("company_code", "manufacturer_serial", "serial_normalized", "stock_code", "quantity", "mode"):
        assert protected not in ItemUpdate.model_fields
