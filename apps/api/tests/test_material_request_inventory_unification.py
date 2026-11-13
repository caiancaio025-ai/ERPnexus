"""Regressões: solicitação avulsa, OS e pedido compartilham o Estoque por recebimento."""
from decimal import Decimal
from pathlib import Path

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.auth.models import User  # noqa: F401
from app.core.models import Base
from app.inventory.models import InventoryItem, InventoryMovement
from app.inventory.purchase_cycle import receive_purchase
from app.purchasing import material_models, models  # noqa: F401
from app.purchasing.material_models import MaterialRequest
from app.purchasing.material_schemas import (
    MaterialRequestCreate, MaterialRequestOutput, MaterialRequestUpdate, StandaloneMaterialRequestCreate,
)


class Adapter:
    def __init__(self, session):
        self.session = session

    async def scalar(self, stmt):
        return self.session.scalar(stmt)

    async def get(self, model, row_id):
        return self.session.get(model, row_id)

    async def flush(self):
        self.session.flush()

    def add(self, model):
        self.session.add(model)


def test_stock_target_optional_at_request_creation_and_editable_until_received():
    assert MaterialRequestCreate(item_name="Resistor 10k").inventory_destination is None
    assert StandaloneMaterialRequestCreate(item_name="Componente 10k", company_code="universo_eletronica").inventory_destination is None
    payload = MaterialRequestUpdate(status="in_transit", inventory_destination="existing", inventory_item_id=21)
    assert payload.inventory_item_id == 21
    assert MaterialRequestOutput.model_fields["inventory_destination"].default is None
    assert MaterialRequest.__table__.c.inventory_item_id.foreign_keys
    assert MaterialRequest.__table__.c.inventory_format_id.foreign_keys


def test_receipt_mapping_is_required_for_new_requests_but_optional_during_request():
    async def consume():
        engine = create_engine("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(engine)
        try:
            with Session(engine) as session:
                db = Adapter(session)
                params = dict(source="request", source_id=101, company_code="universo_eletronica", name="Kit comprado", quantity=5, unit_cost=Decimal("1.50"), user_id=1, source_code="SC-101")
                with pytest.raises(HTTPException) as info:
                    await receive_purchase(db, **params)
                assert info.value.status_code == 422
                movement = await receive_purchase(db, destination="new", stock_name="Resistor 10k PTH", stock_mode="bulk", **params)
                assert session.get(InventoryItem, movement.item_id).name == "Resistor 10k PTH"
                assert session.get(InventoryItem, movement.item_id).quantity == 5
                again = await receive_purchase(db, destination="new", stock_name="Resistor 10k PTH", stock_mode="bulk", **params)
                assert movement.id == again.id
                assert session.query(InventoryMovement).count() == 1
        finally:
            engine.dispose()
    import asyncio
    asyncio.run(consume())


@pytest.mark.asyncio
async def test_two_distinct_requests_can_add_to_same_component_with_idempotency_and_cost():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    try:
        with Session(engine) as session:
            item = InventoryItem(stock_code="EST-00000001", name="Capacitor SMD", category="capacitor", company_code="universo_eletronica", mode="bulk", quantity=30, unit_cost=Decimal("2.00"), created_by=1)
            session.add(item)
            session.flush()
            db = Adapter(session)
            base = dict(source="request", company_code="universo_eletronica", name="Material comercial diferente", quantity=7, unit_cost=Decimal("4.00"), user_id=1, destination="existing", target_item_id=item.id)
            one = await receive_purchase(db, source_id=201, source_code="SC-201", **base)
            repeated = await receive_purchase(db, source_id=201, source_code="SC-201", **base)
            two = await receive_purchase(db, source_id=202, source_code="SC-202", **base)
            assert one.id == repeated.id != two.id
            assert session.get(InventoryItem, item.id).quantity == 44
            assert session.get(InventoryItem, item.id).stock_code == "EST-00000001"
            assert Decimal(session.get(InventoryItem, item.id).unit_cost) == Decimal("2.64")
            assert session.query(InventoryMovement).count() == 2
    finally:
        engine.dispose()


def test_backend_and_ui_connect_requests_in_laboratory_and_purchasing():
    root = Path(__file__).parents[1]
    router = (root / "app/purchasing/router.py").read_text(encoding="utf-8")
    lab = (root / "app/laboratory/router.py").read_text(encoding="utf-8")
    service = (root / "app/purchasing/material_service.py").read_text(encoding="utf-8")
    assert "destination=request.inventory_destination" in router
    assert 'if payload.status == "received" and previous_receipt is None' in router
    assert 'field in payload.model_fields_set' in router
    assert '"inventory_destination", "inventory_item_id"' in lab
    assert 'inventory_destination=item.inventory_destination' in service
    web = root.parent / "web/src/features"
    purchasing = (web / "purchasing/MaterialRequestsPanel.tsx").read_text(encoding="utf-8")
    laboratory = (web / "laboratory/components/MaterialsPanel.tsx").read_text(encoding="utf-8")
    assert 'stockDestinationPayload(stockTarget)' in purchasing
    assert 'stockDestinationPayload(stockTarget)' in laboratory
    assert 'source="laboratory"' in laboratory


def test_migration_is_additive_and_linked_to_prior_head():
    code = (Path(__file__).parents[1] / "migrations/versions/20261026_02_material_request_inventory_target.py").read_text(encoding="utf-8")
    assert 'down_revision: str | None = "20261026_01"' in code
    assert 'op.add_column("material_requests"' in code
    assert "op.drop_table" not in code
