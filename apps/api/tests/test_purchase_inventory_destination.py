"""Contrato: compra e SKU são distintos, entrada opcional até a chegada."""
from datetime import date, timedelta
from decimal import Decimal

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.auth.models import User  # noqa: F401
from app.core.models import Base
from app.inventory.models import InventoryItem, InventoryMovement
from app.inventory.purchase_cycle import receive_purchase
from app.purchasing import material_models, models  # noqa: F401
from app.purchasing.schemas import PurchaseInput

class Adapter:
    def __init__(self, session): self.session = session
    async def scalar(self, query): return self.session.scalar(query)
    async def flush(self): self.session.flush()
    async def get(self, model, row_id): return self.session.get(model, row_id)
    def add(self, obj): self.session.add(obj)


def purchase(**kw):
    fields = dict(company_code="universo_eletronica", supplier_id=1,
                  product_name="Lote comprado com descrição comercial", quantity=4,
                  total_amount=Decimal("100.00"), purchase_date=date.today(),
                  estimated_delivery_date=date.today()+timedelta(days=3))
    fields.update(kw)
    return PurchaseInput(**fields)


def test_purchase_optional_mapping_before_delivery_and_mandatory_when_delivered():
    assert purchase().inventory_destination is None
    assert purchase(inventory_name="Capacitor SMD 100nF").product_name.startswith("Lote comprado")
    # Compatibilidade com pedidos da V2 que já foram entregues e não tinham
    # destino persistido. A primeira entrada nova continua protegida no serviço.
    assert purchase(status="delivered").inventory_destination is None
    with pytest.raises(ValueError, match="Selecione"):
        purchase(status="delivered", inventory_destination="existing")
    with pytest.raises(ValueError, match="série"):
        purchase(status="delivered", inventory_destination="new", inventory_name="Módulo industrial", inventory_mode="serialized")
    assert purchase(status="delivered", inventory_destination="existing", inventory_item_id=22).inventory_item_id == 22
    assert purchase(status="delivered", inventory_destination="new", inventory_mode="bulk", inventory_name="Capacitor 100nF").inventory_name == "Capacitor 100nF"


@pytest.mark.asyncio
async def test_receipt_existing_increases_quantity_same_sku_and_weighted_cost():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        target = InventoryItem(id=3, stock_code="EST-00000003", company_code="universo_eletronica",
                               name="Resistor 10k SMD", category="resistor", mode="bulk",
                               quantity=10, unit_cost=Decimal("2.00"), created_by=1)
        session.add(target); session.flush()
        db=Adapter(session)
        with pytest.raises(HTTPException) as no_target:
            await receive_purchase(db, source="order", source_id=999, company_code="universo_eletronica",
                                   name="Sem destino", quantity=1, unit_cost=Decimal("1"),
                                   user_id=1, source_code="PC-999")
        assert no_target.value.status_code == 422
        kw=dict(source="order", source_id=44, company_code="universo_eletronica", name="Compra caixa de resistores",
                quantity=5, unit_cost=Decimal("4.00"), user_id=1, source_code="PC-44",
                destination="existing", target_item_id=target.id)
        move=await receive_purchase(db,**kw)
        assert move.item_id == 3
        assert move.quantity == 5
        assert session.get(InventoryItem,3).quantity == 15
        assert session.get(InventoryItem,3).stock_code == "EST-00000003"
        assert Decimal(session.get(InventoryItem,3).unit_cost) == Decimal("2.67")
        repeated=await receive_purchase(db,**kw)
        assert repeated.id == move.id
        assert session.get(InventoryItem,3).quantity == 15
        assert session.query(InventoryMovement).count() == 1
        with pytest.raises(HTTPException) as exc:
            await receive_purchase(db,**{**kw, "source_id":45, "company_code":"universo_automacao"})
        assert exc.value.status_code == 422
    engine.dispose()


@pytest.mark.asyncio
async def test_new_serialized_purchase_has_unique_serial_and_quantity_one():
    engine = create_engine("sqlite+pysqlite:///:memory:");Base.metadata.create_all(engine)
    with Session(engine) as session:
        db=Adapter(session)
        base=dict(source="order", source_id=91, company_code="universo_eletronica",name="Compra drive",
                  quantity=1,unit_cost=Decimal("300.00"),user_id=1,source_code="PC-91",destination="new",
                  stock_name="Módulo SINAMICS",stock_mode="serialized",stock_serial="SN-002",stock_category="modulo")
        movement=await receive_purchase(db,**base)
        item=session.get(InventoryItem,movement.item_id)
        assert item.name == "Módulo SINAMICS" and item.manufacturer_serial == "SN-002"
        assert item.quantity == 1 and item.slot_id is None
        assert item.serial_normalized == "SN-002" and item.stock_code.startswith("EST-")
        with pytest.raises(HTTPException):
            await receive_purchase(db,**{**base, "source_id":92,"quantity":3})
    engine.dispose()


def test_new_migration_is_incremental_and_designed_for_preservation():
    from pathlib import Path
    path=Path(__file__).parents[1]/"migrations"/"versions"/"20261026_01_purchase_inventory_target.py"
    sql=path.read_text()
    assert 'down_revision: str | None = "20261022_02"' in sql
    assert 'purchase_orders' in sql and 'inventory_item_id' in sql
    assert 'op.drop_table' not in sql
