from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import HTTPException
from sqlalchemy.dialects import postgresql

from app.commercial import router as commercial_router
from app.commercial.schemas import CommercialEquipmentInput


def _db_for_creation(equipment_id: int):
    db = SimpleNamespace(
        scalar=AsyncMock(return_value=equipment_id),
        add=Mock(),
        flush=AsyncMock(),
        commit=AsyncMock(),
        refresh=AsyncMock(),
    )

    async def verify_first_flush():
        row = db.add.call_args.args[0]
        assert row.id == equipment_id
        assert row.serial_code == f"{equipment_id:03d}"
        assert row.patrimony_code == f"PAT-{equipment_id:06d}"
        assert row.quantity == 1

    db.flush.side_effect = verify_first_flush
    return db


@pytest.mark.asyncio
async def test_creating_patrimony_provides_codes_before_first_database_flush(monkeypatch):
    db = _db_for_creation(3)
    monkeypatch.setattr(
        commercial_router,
        "_commercial_equipment_output",
        AsyncMock(side_effect=lambda row, user: row),
    )
    payload = CommercialEquipmentInput(equipment_type="Inversor CFW11", quantity=1)

    row = await commercial_router.create_equipment(payload, SimpleNamespace(id=1), db)

    assert row.patrimony_code == "PAT-000003"
    assert row.serial_code == "003"
    assert db.scalar.await_count == 1
    statement = db.scalar.call_args.args[0]
    sql = str(statement.compile(dialect=postgresql.dialect())).lower()
    assert "nextval(pg_get_serial_sequence(" in sql
    assert "commercial_equipment" in [
        str(value) for value in statement.compile(dialect=postgresql.dialect()).params.values()
    ]
    db.flush.assert_awaited_once()
    db.commit.assert_awaited_once()
    db.refresh.assert_awaited_once_with(row)


@pytest.mark.asyncio
async def test_patrimony_location_is_assigned_after_identifiers(monkeypatch):
    db = _db_for_creation(42)
    location = SimpleNamespace(id=17, code="PA1")
    get_location = AsyncMock(return_value=location)
    set_location = AsyncMock()
    monkeypatch.setattr(commercial_router, "_asset_location_or_404", get_location)
    monkeypatch.setattr(commercial_router, "_set_asset_location", set_location)
    monkeypatch.setattr(
        commercial_router,
        "_commercial_equipment_output",
        AsyncMock(side_effect=lambda row, user: row),
    )

    payload = CommercialEquipmentInput(
        equipment_type="Inversor CFW11", quantity=1, asset_location_id=17
    )
    row = await commercial_router.create_equipment(payload, SimpleNamespace(id=1), db)

    get_location.assert_awaited_once_with(db, 17)
    set_location.assert_awaited_once_with(db, row, location, user_id=1)
    db.flush.assert_awaited_once()
    db.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_creation_rejects_money_fields_without_permission_before_insert(monkeypatch):
    db = _db_for_creation(7)

    def forbid_money(_user):
        raise HTTPException(status_code=403, detail="Sem permissão")

    monkeypatch.setattr(commercial_router, "_require_money", forbid_money)
    payload = CommercialEquipmentInput(
        equipment_type="Inversor CFW11", quantity=1, unit_cost=1500
    )

    with pytest.raises(HTTPException) as error:
        await commercial_router.create_equipment(payload, SimpleNamespace(id=1), db)

    assert error.value.status_code == 403
    db.scalar.assert_not_awaited()
    db.add.assert_not_called()
    db.commit.assert_not_awaited()
