"""Segurança da entrada automática, formatação, idempotência e custos."""
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.auth.models import User  # noqa: F401
from app.core.models import Base
from app.inventory.models import InventoryComponentFormat, InventoryItem, InventoryMovement
from app.inventory.purchase_cycle import purchase_unit_cost, receive_purchase
from app.inventory.schemas import ItemInput, ItemUpdate, FormatInput
from app.purchasing import material_models, models  # noqa: F401
from app.purchasing.material_service import recalculate_work_order_parts_cost


def test_formats_are_extendable_but_bound_to_a_category():
    valid = FormatInput(category="resistor", code="smd-1206", name="SMD 1206")
    assert valid.code == "smd-1206"
    with pytest.raises(ValueError):
        FormatInput(category="resistor", code="código inválido", name="1206")
    item = ItemInput(company_code="universo_eletronica", name="Resistor 10k", category="resistor", format_id=123, mode="bulk", quantity=500)
    assert item.format_id == 123
    assert "format_id" in ItemUpdate.model_fields
    assert "uq_inv_format_category_code" in {c.name for c in InventoryComponentFormat.__table__.constraints}


def test_serialized_still_requires_one_unit_and_unique_serial():
    with pytest.raises(ValueError):
        ItemInput(company_code="universo_eletronica", name="Drive", mode="serialized", manufacturer_serial="SN-001", quantity=3)
    assert InventoryItem.__table__.c.serial_normalized is not None


def test_receipt_rounding_and_invalid_quantity():
    assert purchase_unit_cost(Decimal("10.00"), 3) == Decimal("3.33")
    with pytest.raises(HTTPException):
        purchase_unit_cost(Decimal("2.00"), 0)


@pytest.mark.asyncio
async def test_received_purchase_is_idempotent_and_request_can_share_the_same_receipt():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    class Adapter:
        def __init__(self, session): self.session = session
        async def scalar(self, query): return self.session.scalar(query)
        async def flush(self): self.session.flush()
        def add(self, obj): self.session.add(obj)
    with Session(engine) as session:
        db = Adapter(session)
        params = dict(company_code="universo_eletronica", name="Capacitor 470uF", quantity=50, unit_cost=Decimal("3.20"), user_id=1)
        original = await receive_purchase(db, source="order", source_id=123, source_code="PC-123", destination="new", **params)
        same = await receive_purchase(db, source="order", source_id=123, source_code="PC-123", destination="new", **params)
        assert same.id == original.id
        linked = await receive_purchase(db, source="request", source_id=456, source_code="SC-456", linked_source_id=123, **params)
        assert linked.id == original.id
        assert linked.purchase_order_id == 123 and linked.material_request_id == 456
        assert session.scalar(select(InventoryItem.quantity)) == 50
        assert session.query(InventoryItem).count() == 1
        assert session.query(InventoryMovement).count() == 1
        with pytest.raises(HTTPException) as error:
            await receive_purchase(db, source="request", source_id=457, source_code="SC-457", linked_source_id=123, **{**params, "quantity": 51})
        assert error.value.status_code == 409
    engine.dispose()


def test_receipt_uniqueness_and_fk_provenance():
    for field in ("purchase_order_id", "material_request_id"):
        assert InventoryMovement.__table__.c[field].unique is True
        assert InventoryMovement.__table__.c[field].foreign_keys


def test_os_cost_query_skips_purchased_material_already_stocked():
    # Este guard protege a fonte canônica de custo de dupla contagem.
    import inspect
    source = inspect.getsource(recalculate_work_order_parts_cost)
    assert "~stocked_request" in source
    assert "await consumed_cost" in source
