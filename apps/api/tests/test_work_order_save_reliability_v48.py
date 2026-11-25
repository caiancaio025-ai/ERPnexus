"""Regressões de gravação da O.S. com sessão assíncrona e persistência real.

SQLite verifica o contrato/efeitos da gravação. Os bloqueios PostgreSQL são
verificados também na suíte de integração concorrente, em banco PostgreSQL.
"""

from datetime import date
from decimal import Decimal

import pytest
import pytest_asyncio
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import event, func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.auth.models import User
from app.commercial import router as commercial
from app.commercial.models import CommercialCompanyProfile, CommercialQuote
from app.commercial.schemas import CommercialQuoteInput
from app.core.models import Base
from app.inventory import models as inventory_models  # noqa: F401
from app.laboratory import router as laboratory
from app.laboratory.models import LaboratoryCustomer, LaboratoryEquipment, LaboratoryWorkOrder
from app.laboratory.schemas import WorkOrderInput, WorkOrderUpdate
from app.purchasing import material_models, models as purchase_models  # noqa: F401


@pytest_asyncio.fixture
async def saved_work_order():
    pytest.importorskip("aiosqlite")
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    @event.listens_for(engine.sync_engine, "connect")
    def enforce_foreign_keys(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")

    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    sessions = async_sessionmaker(engine, expire_on_commit=False, autoflush=False)
    async with sessions() as db:
        actor = User(name="Teste", email="teste@example.test", username="teste", password_hash="unused", role="gestao")
        db.add(actor)
        await db.flush()
        company = CommercialCompanyProfile(company_code="universo_eletronica", legal_name="Universo", created_by=actor.id)
        customer = LaboratoryCustomer(company_code=company.company_code, legal_name="Cliente", created_by=actor.id)
        db.add_all([company, customer])
        await db.flush()
        equipment = LaboratoryEquipment(company_code=company.company_code, customer_id=customer.id, customer_name=customer.legal_name,
            serial_number=None, serial_normalized=None, manufacturer="WEG", model="CFW11", power="10 CV", created_by=actor.id)
        db.add(equipment)
        await db.flush()
        order = LaboratoryWorkOrder(number="OS-99999", company_code=company.company_code, equipment_id=equipment.id,
            customer_id=customer.id, customer_name=customer.legal_name, reported_defect="Falha inicial", opened_at=date.today(),
            entry_invoice="NF-123", priority="high", internal_notes="Preservar observação", parts_cost=Decimal("19.50"),
            created_by=actor.id)
        db.add(order)
        await db.commit()
        ids = (actor.id, order.id, equipment.id, customer.id)
    try:
        yield sessions, ids
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_partial_patch_preserves_omitted_fields_and_equipment_identity(saved_work_order):
    sessions, (user_id, order_id, equipment_id, _) = saved_work_order
    async with sessions() as db:
        actor = await db.get(User, user_id)
        result = await laboratory.update_work_order(order_id, WorkOrderUpdate(version=1, reported_defect="Laudo alterado"), actor, db)
        assert result.reported_defect == "Laudo alterado"
        assert result.entry_invoice == "NF-123"
        assert result.priority == "high"
        assert result.internal_notes == "Preservar observação"
        assert result.parts_cost == Decimal("19.50")
        assert result.equipment_id == equipment_id
        assert result.version == 2
        # Salvar a mesma O.S. sem serial não pode criar um equipamento a cada vez.
        for number in range(3):
            result = await laboratory.update_work_order(order_id,
                WorkOrderUpdate(version=result.version, internal_notes=f"Observação {number}"), actor, db)
        assert await db.scalar(select(func.count(LaboratoryEquipment.id))) == 1
        assert result.equipment_id == equipment_id
    async with sessions() as db:
        stored = await db.get(LaboratoryWorkOrder, order_id)
        assert stored.internal_notes == "Observação 2"
        assert stored.entry_invoice == "NF-123"


@pytest.mark.asyncio
async def test_clearing_equipment_fields_is_persisted(saved_work_order):
    sessions, (user_id, order_id, equipment_id, _) = saved_work_order
    async with sessions() as db:
        actor = await db.get(User, user_id)
        result = await laboratory.update_work_order(order_id,
            WorkOrderUpdate(version=1, manufacturer=None, model=None, power=None), actor, db)
        assert result.manufacturer is None
        assert result.model is None
        assert result.power is None
        assert result.equipment_id == equipment_id
    async with sessions() as db:
        equipment = await db.get(LaboratoryEquipment, equipment_id)
        assert equipment.model is None and equipment.manufacturer is None and equipment.power is None


@pytest.mark.asyncio
async def test_unrelated_edit_allows_existing_inactive_customer(saved_work_order):
    sessions, (user_id, order_id, _, customer_id) = saved_work_order
    async with sessions() as db:
        customer = await db.get(LaboratoryCustomer, customer_id)
        customer.is_active = False
        await db.commit()
        actor = await db.get(User, user_id)
        result = await laboratory.update_work_order(order_id,
            WorkOrderUpdate(version=1, customer_notes="Contato atualizado"), actor, db)
        assert result.customer_notes == "Contato atualizado"
        assert result.customer_id == customer_id


@pytest.mark.asyncio
async def test_stale_version_does_not_overwrite_another_save(saved_work_order):
    sessions, (user_id, order_id, _, _) = saved_work_order
    async with sessions() as db:
        actor = await db.get(User, user_id)
        await laboratory.update_work_order(order_id, WorkOrderUpdate(version=1, internal_notes="Primeiro salvo"), actor, db)
    async with sessions() as db:
        actor = await db.get(User, user_id)
        with pytest.raises(HTTPException) as failure:
            await laboratory.update_work_order(order_id, WorkOrderUpdate(version=1, internal_notes="Sobrescrever"), actor, db)
        assert failure.value.status_code == 409
    async with sessions() as db:
        stored = await db.get(LaboratoryWorkOrder, order_id)
        assert stored.internal_notes == "Primeiro salvo" and stored.version == 2


@pytest.mark.asyncio
async def test_monetary_patch_is_normalized_and_confirmed_by_database(saved_work_order):
    sessions, (user_id, order_id, _, _) = saved_work_order
    async with sessions() as db:
        actor = await db.get(User, user_id)
        result = await laboratory.update_work_order(order_id,
            WorkOrderUpdate(version=1, approved_value="1.234,56", parts_cost="0"), actor, db)
        assert result.approved_value == Decimal("1234.56")
        assert result.parts_cost == Decimal("0.00")
        result = await laboratory.update_work_order(order_id,
            WorkOrderUpdate(version=result.version, internal_notes="Valor zero mantido"), actor, db)
        assert result.parts_cost == Decimal("0.00")
    async with sessions() as db:
        stored = await db.get(LaboratoryWorkOrder, order_id)
        assert stored.approved_value == Decimal("1234.56")
        assert stored.parts_cost == Decimal("0.00")


@pytest.mark.asyncio
async def test_empty_patch_does_not_change_version(saved_work_order):
    sessions, (user_id, order_id, _, _) = saved_work_order
    async with sessions() as db:
        result = await laboratory.update_work_order(order_id, WorkOrderUpdate(version=1), await db.get(User, user_id), db)
        assert result.version == 1


@pytest.mark.parametrize("value", ["NaN", "Infinity", "-1", "1.001", "1000000000000", "1,234.56", "abc"])
def test_invalid_work_order_money_is_rejected_before_database(value):
    with pytest.raises(ValidationError):
        WorkOrderUpdate(version=1, approved_value=value)


@pytest.mark.parametrize("field,value", [("manufacturer", "X" * 121), ("model", "X" * 161), ("serial_number", "X" * 121), ("power", "X" * 81)])
def test_equipment_database_lengths_are_validated(field, value):
    with pytest.raises(ValidationError):
        WorkOrderUpdate(version=1, **{field: value})


@pytest.mark.parametrize("field", ["company_code", "customer_name", "reported_defect"])
def test_required_work_order_fields_cannot_be_cleared_with_null(field):
    with pytest.raises(ValidationError):
        WorkOrderUpdate(version=1, **{field: None})


@pytest.mark.asyncio
async def test_commercial_revision_from_old_source_advances_without_duplicate(saved_work_order):
    sessions, (user_id, _, _, customer_id) = saved_work_order
    async with sessions() as db:
        actor = await db.get(User, user_id)
        payload = CommercialQuoteInput(quote_type="sale", company_code="universo_eletronica", customer_id=customer_id,
            items=[{"description": "Equipamento", "quantity": 1, "unit_price": 1500}])
        original = await commercial.create_quote(payload, actor, db)
        issued = await commercial.issue_quote(original.id, actor, db)
        assert issued.revision == 1
        second = await commercial.revise_quote(original.id, actor, db)
        assert second.revision == 2
        same = await commercial.revise_quote(original.id, actor, db)
        assert same.id == second.id
        await commercial.issue_quote(second.id, actor, db)
        third = await commercial.revise_quote(original.id, actor, db)
        assert third.revision == 3
        assert third.total == 1500
        assert await db.scalar(select(func.count(CommercialQuote.id))) == 3
