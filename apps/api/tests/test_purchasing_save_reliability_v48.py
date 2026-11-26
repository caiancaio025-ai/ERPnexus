"""Behavioral regressions for real async transactions in purchasing/stock.

The suite uses the production autoflush=False setting; source-code assertions
alone missed lost form fields, stale cost sums and errors after successful saves.
"""
from datetime import date, timedelta
from decimal import Decimal

import pytest
import pytest_asyncio
from fastapi import HTTPException
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.main import app  # noqa: F401 — registers every model/FK
from app.auth.models import User
from app.core.models import Base
from app.inventory.models import InventoryItem, InventoryMovement
from app.inventory.purchase_cycle import receive_purchase
from app.inventory.service import move_stock
from app.laboratory.models import LaboratoryEquipment, LaboratoryWorkOrder
from app.notifications.models import Notification
from app.purchasing import router as purchasing
from app.purchasing.material_models import MaterialRequest
from app.purchasing.material_schemas import MaterialRequestUpdate, StandaloneMaterialRequestCreate
from app.purchasing.material_service import next_material_request_code
from app.purchasing.models import PurchaseOrder, Supplier
from app.purchasing.schemas import PurchaseInput, PurchaseUpdate
from app.purchasing.service import next_purchase_code


@pytest_asyncio.fixture
async def context():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
    async with factory() as db:
        user = User(name="Gestão Teste", username="save-test", email="save@example.test",
                    password_hash="test-only", role="gestao", modules=["compras", "laboratorio"])
        supplier = Supplier(name="Fornecedor dos testes", origin="national")
        db.add_all([user, supplier])
        await db.flush()
        from inventory_test_catalog import receipt_catalog_rows
        db.add_all(receipt_catalog_rows(user_id=user.id))
        equipment = LaboratoryEquipment(company_code="universo_eletronica",
                                        customer_name="Cliente", created_by=user.id)
        db.add(equipment)
        await db.flush()
        order = LaboratoryWorkOrder(number="OS-TESTE-1", company_code="universo_eletronica",
                                    equipment_id=equipment.id, customer_name="Cliente",
                                    reported_defect="Não liga", opened_at=date.today(),
                                    created_by=user.id)
        db.add(order)
        await db.commit()
        yield db, user, supplier, order
    await engine.dispose()


def order_payload(supplier_id, **extra):
    data = dict(company_code="universo_eletronica", supplier_id=supplier_id,
                product_name="Kit de capacitores", quantity=4, total_amount=Decimal("40.00"),
                purchase_date=date.today(), estimated_delivery_date=date.today() + timedelta(days=2),
                inventory_destination="new", inventory_name="Capacitor 470uF",
                inventory_mode="bulk", inventory_category="componentes")
    data.update(extra)
    return PurchaseInput(**data)


async def material(db, user, order, **extra):
    data = dict(code="SC-TESTE-1", company_code="universo_eletronica", work_order_id=order.id,
                equipment_id=order.equipment_id, requester_user_id=user.id, item_name="Resistor",
                quantity=4, priority="normal", status="purchasing", supplier_name="Fornecedor",
                purchase_reference="IMPORT-123", purchase_link="https://example.test/item",
                tracking_code="TRACK-123", unit_cost=Decimal("12.50"),
                expected_delivery_date=date.today() + timedelta(days=2))
    data.update(extra)
    request = MaterialRequest(**data)
    db.add(request)
    await db.commit()
    return request


@pytest.mark.asyncio
async def test_purchase_create_get_and_update_preserve_inventory_mapping(context):
    db, user, supplier, _ = context
    payload = order_payload(supplier.id)
    created = await purchasing.create_order(payload, user, db)
    assert created.inventory_destination == "new"
    assert created.inventory_name == "Capacitor 470uF"
    fetched = await purchasing.get_order(created.id, user, db)
    assert fetched.model_dump()["inventory_mode"] == "bulk"
    edited = await purchasing.update_order(
        created.id, PurchaseUpdate(**{**payload.model_dump(), "notes": "Conferido"}), user, db,
    )
    assert edited.notes == "Conferido"
    assert edited.inventory_name == created.inventory_name
    assert (await db.get(PurchaseOrder, created.id)).notes == "Conferido"


@pytest.mark.asyncio
async def test_received_purchase_can_edit_notes_even_if_legacy_client_omits_stock_fields(context):
    db, user, supplier, _ = context
    payload = order_payload(supplier.id, status="delivered")
    created = await purchasing.create_order(payload, user, db)
    legacy = {k: v for k, v in payload.model_dump().items() if not k.startswith("inventory_")}
    legacy["notes"] = "Nota fiscal conferida"
    edited = await purchasing.update_order(created.id, PurchaseUpdate(**legacy), user, db)
    assert edited.notes == "Nota fiscal conferida"
    assert edited.inventory_destination == "new"
    assert edited.inventory_name == "Capacitor 470uF"
    assert await db.scalar(select(func.count()).select_from(InventoryMovement)) == 1
    assert await db.scalar(select(InventoryItem.quantity)) == 4


@pytest.mark.asyncio
async def test_received_purchase_still_refuses_physical_changes_and_delete(context):
    db, user, supplier, _ = context
    payload = order_payload(supplier.id, status="delivered")
    created = await purchasing.create_order(payload, user, db)
    with pytest.raises(HTTPException) as error:
        await purchasing.update_order(created.id, PurchaseUpdate(**{
            **payload.model_dump(), "quantity": 5,
        }), user, db)
    assert error.value.status_code == 409
    with pytest.raises(HTTPException) as error:
        await purchasing.delete_order(created.id, user, db)
    assert error.value.status_code == 409
    assert await db.scalar(select(InventoryItem.quantity)) == 4
    assert (await db.get(PurchaseOrder, created.id)).is_deleted is False


@pytest.mark.asyncio
async def test_legacy_delivered_purchase_can_edit_notes_without_backfilling_receipt_or_date(context):
    db, user, supplier, _ = context
    payload = order_payload(supplier.id, status="delivered", inventory_destination=None,
                            inventory_name=None, inventory_mode=None, inventory_category=None)
    purchase = PurchaseOrder(**payload.model_dump(), code="PC-LEGACY-1",
                             supplier_name=supplier.name, created_by=user.id)
    db.add(purchase)
    await db.commit()
    result = await purchasing.update_order(purchase.id, PurchaseUpdate(**{
        **payload.model_dump(), "notes": "Documento conferido",
    }), user, db)
    assert result.notes == "Documento conferido"
    assert result.delivered_at is None
    assert await db.scalar(select(func.count()).select_from(InventoryMovement)) == 0


@pytest.mark.asyncio
async def test_legacy_received_request_can_edit_metadata_without_backfilling_stock(context):
    db, user, _, order = context
    request = await material(db, user, order, status="received")
    result = await purchasing.update_material_request(request.id, MaterialRequestUpdate(
        status="received", tracking_code="PROTOCOLO-CORRIGIDO",
    ), user, db)
    assert result.tracking_code == "PROTOCOLO-CORRIGIDO"
    assert result.unit_cost == Decimal("12.50")
    assert await db.scalar(select(func.count()).select_from(InventoryMovement)) == 0


@pytest.mark.asyncio
async def test_partial_request_update_preserves_cost_and_metadata_and_recalculates_os(context):
    db, user, _, order = context
    request = await material(db, user, order)
    result = await purchasing.update_material_request(
        request.id, MaterialRequestUpdate(status="purchased"), user, db,
    )
    assert result.unit_cost == Decimal("12.50")
    assert result.supplier_name == "Fornecedor"
    assert result.tracking_code == "TRACK-123"
    assert result.purchase_reference == "IMPORT-123"
    await db.refresh(order)
    assert order.parts_cost == Decimal("50.00")
    result = await purchasing.update_material_request(
        request.id, MaterialRequestUpdate(status="in_transit", tracking_code="NOVO"), user, db,
    )
    assert result.tracking_code == "NOVO"
    assert result.unit_cost == Decimal("12.50")
    assert result.purchase_link == "https://example.test/item"
    await purchasing.update_material_request(
        request.id, MaterialRequestUpdate(status="cancelled"), user, db,
    )
    await db.refresh(order)
    assert order.parts_cost == Decimal("0.00")


@pytest.mark.asyncio
async def test_same_status_cost_edit_is_included_immediately_in_os_total(context):
    db, user, _, order = context
    request = await material(db, user, order, status="purchased")
    await purchasing.update_material_request(
        request.id, MaterialRequestUpdate(status="purchased", unit_cost=Decimal("25.00")), user, db,
    )
    await db.refresh(order)
    assert order.parts_cost == Decimal("100.00")


@pytest.mark.asyncio
async def test_received_material_cannot_clear_historical_cost(context):
    db, user, _, order = context
    request = await material(db, user, order, status="purchased", inventory_destination="new",
                             inventory_name="Resistor 1k", inventory_mode="bulk")
    received = await purchasing.update_material_request(
        request.id, MaterialRequestUpdate(status="received"), user, db,
    )
    assert received.unit_cost == Decimal("12.50")
    assert await db.scalar(select(InventoryItem.quantity)) == 4
    with pytest.raises(HTTPException) as error:
        await purchasing.update_material_request(
            request.id, MaterialRequestUpdate(status="delivered_to_lab", unit_cost=None), user, db,
        )
    assert error.value.status_code == 409
    assert request.unit_cost == Decimal("12.50")
    await db.refresh(order)
    assert order.parts_cost == Decimal("0.00")  # counted only when issued from stock


@pytest.mark.asyncio
async def test_received_material_can_advance_without_resending_inventory_or_cost(context):
    db, user, _, order = context
    request = await material(db, user, order, status="purchased", inventory_destination="new",
                             inventory_name="Resistor 1k", inventory_mode="bulk")
    await purchasing.update_material_request(request.id, MaterialRequestUpdate(status="received"), user, db)
    final = await purchasing.update_material_request(
        request.id, MaterialRequestUpdate(status="delivered_to_lab", note="Material conferido"), user, db,
    )
    assert final.unit_cost == Decimal("12.50")
    assert final.inventory_name == "Resistor 1k"
    assert await db.scalar(select(func.count()).select_from(InventoryMovement)) == 1


@pytest.mark.asyncio
async def test_receipt_cannot_steal_link_from_another_request(context):
    db, user, _, _ = context
    common = dict(company_code="universo_eletronica", name="Resistor", quantity=4,
                  unit_cost=Decimal("12.50"), user_id=user.id, destination="new")
    first = await receive_purchase(db, source="order", source_id=11, source_code="PC-11", **common)
    await receive_purchase(db, source="request", source_id=22, source_code="SC-22",
                           linked_source_id=11, **common)
    with pytest.raises(HTTPException) as error:
        await receive_purchase(db, source="request", source_id=33, source_code="SC-33",
                               linked_source_id=11, **common)
    assert error.value.status_code == 409
    assert first.material_request_id == 22
    assert await db.scalar(select(func.count()).select_from(InventoryMovement)) == 1
    assert await db.scalar(select(InventoryItem.quantity)) == 4


@pytest.mark.asyncio
async def test_receiving_into_existing_stock_reloads_quantity_after_acquiring_lock(context):
    db, user, _, _ = context
    item = InventoryItem(stock_code="EST-LOCK-1", company_code="universo_eletronica",
                         name="Resistor", mode="bulk", quantity=10,
                         unit_cost=Decimal("2.00"), created_by=user.id)
    db.add(item)
    await db.commit()
    # Simula o dado desatualizado que o editor carregou antes de esperar pelo lock.
    await db.execute(update(InventoryItem).where(InventoryItem.id == item.id)
                     .values(quantity=20, unit_cost=Decimal("3.00"))
                     .execution_options(synchronize_session=False))
    assert item.quantity == 10
    await receive_purchase(db, source="order", source_id=19, source_code="PC-19",
                           company_code=item.company_code, name=item.name, quantity=5,
                           unit_cost=Decimal("4.00"), user_id=user.id,
                           destination="existing", target_item_id=item.id)
    assert item.quantity == 25
    assert item.unit_cost == Decimal("3.20")


@pytest.mark.asyncio
async def test_issuing_stock_does_not_use_a_previously_loaded_obsolete_balance(context):
    db, user, _, order = context
    item = InventoryItem(stock_code="EST-LOCK-2", company_code=order.company_code,
                         name="Capacitor", mode="bulk", quantity=5,
                         unit_cost=Decimal("2.00"), created_by=user.id)
    db.add(item)
    await db.commit()
    await db.execute(update(InventoryItem).where(InventoryItem.id == item.id)
                     .values(quantity=1).execution_options(synchronize_session=False))
    assert item.quantity == 5
    with pytest.raises(HTTPException) as error:
        await move_stock(db, item_id=item.id, quantity=3, kind="issue",
                         user_id=user.id, work_order_id=order.id)
    assert error.value.status_code == 409
    assert await db.scalar(select(InventoryItem.quantity)) == 1
    assert await db.scalar(select(func.count()).select_from(InventoryMovement)) == 0


@pytest.mark.asyncio
async def test_numbering_uses_largest_suffix_even_if_last_imported_row_is_older(context):
    db, user, supplier, order = context
    year = date.today().year
    for suffix in ("10000", "0099", "LEGADO"):
        db.add(PurchaseOrder(**order_payload(supplier.id).model_dump(), code=f"PC-{year}-{suffix}",
                             supplier_name=supplier.name, created_by=user.id))
        db.add(MaterialRequest(code=f"SC-{year}-{suffix}", company_code=order.company_code,
                               work_order_id=order.id, requester_user_id=user.id,
                               item_name="Componente", quantity=1))
    await db.flush()
    assert await next_purchase_code(db) == f"PC-{year}-10001"
    assert await next_material_request_code(db) == f"SC-{year}-10001"


@pytest.mark.asyncio
async def test_response_validation_failure_does_not_commit_purchase(context, monkeypatch):
    db, user, supplier, _ = context
    def fail_response(*args, **kwargs):
        raise ValueError("Simulated response serialization failure")
    monkeypatch.setattr(purchasing, "_purchase_output", fail_response)
    with pytest.raises(ValueError, match="serialization"):
        await purchasing.create_order(order_payload(supplier.id), user, db)
    await db.rollback()  # same cleanup as get_db after an endpoint exception
    assert await db.scalar(select(func.count()).select_from(PurchaseOrder)) == 0
    assert await db.scalar(select(func.count()).select_from(Notification)) == 0


@pytest.mark.asyncio
async def test_standalone_creation_returns_saved_inventory_target(context):
    db, user, _, _ = context
    result = await purchasing.create_standalone_material_request(StandaloneMaterialRequestCreate(
        company_code="universo_eletronica", item_name="Capacitores", quantity=5,
        inventory_destination="new", inventory_name="Capacitor SMD", inventory_mode="bulk",
    ), user, db)
    assert result.id > 0
    assert result.inventory_name == "Capacitor SMD"
    assert result.status == "awaiting_approval"
    assert (await db.get(MaterialRequest, result.id)).inventory_name == result.inventory_name
