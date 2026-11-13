"""Regressão V14: pesquisa documental, exclusão segura, etiqueta de locação."""
from datetime import date
from io import BytesIO
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.commercial.label_pdf import commercial_label_pdf
from app.customers.service import list_customer_documents_page


def _equipment(status="rented"):
    return SimpleNamespace(
        id=15, patrimony_code="PAT-000015", equipment_type="INVERSOR WEG CFW11",
        manufacturer="WEG", model="CFW11", manufacturer_serial="BR-9988",
        location="Estante A4", stock_status=status,
    )


def test_customer_name_on_rental_label_only():
    from app.commercial.label_pdf import _rental_customer_lines
    assert commercial_label_pdf(_equipment(), "USINA MONTE BELO").startswith(b"%PDF")
    assert commercial_label_pdf(_equipment("available"), "USINA MONTE BELO").startswith(b"%PDF")
    assert "USINA MONTE BELO" in " ".join(_rental_customer_lines("USINA MONTE BELO", 110))


@pytest.mark.asyncio
async def test_document_search_filters_before_page_and_matches_all_fields():
    db = AsyncMock()
    db.scalar.return_value = 2
    result = MagicMock(); result.all.return_value = []
    db.scalars.return_value = result
    page = await list_customer_documents_page(
        db, customer_id=18, page=1, page_size=50,
        search="manutencao", category="contract", issue_date=date(2026, 10, 28),
    )
    assert page.total == 2
    query = db.scalars.await_args.args[0]
    sql = str(query.compile(compile_kwargs={"literal_binds": True})).lower()
    for field in ("customer_documents.customer_id", "reference_number", "original_name", "notes", "category", "issue_date"):
        assert field in sql
    assert "contract" in sql and "2026-10-28" in sql and "manutencao" in sql
    count_sql = str(db.scalar.await_args.args[0].compile(compile_kwargs={"literal_binds": True})).lower()
    assert "contract" in count_sql and "manutencao" in count_sql


def test_inventory_delete_handlers_guard_historical_references():
    from pathlib import Path
    source = (Path(__file__).parents[1] / "app/inventory/router.py").read_text()
    assert '@router.delete("/areas/{area_id}", status_code=204)' in source
    assert '@router.delete("/types/{type_id}", status_code=204)' in source
    assert '@router.delete("/containers/{container_id}")' in source
    assert 'InventoryLocationHistory.previous_slot_id.in_(slot_ids)' in source
    assert 'InventoryLocationHistory.new_slot_id.in_(slot_ids)' in source
    assert 'await db.delete(slot)' in source
    assert 'await db.delete(container)' in source


def test_rental_customer_validation_and_migration_present():
    from pathlib import Path
    root = Path(__file__).parents[1]
    router = (root / "app/commercial/router.py").read_text()
    assert 'customer.company_code != company_code' in router
    assert 'customer_id is None' in router
    assert 'rental_customer_name = customer.trade_name or customer.legal_name' in router
    assert 'commercial_label_pdf, row, rental_customer_name' in router
    migration = (root / "migrations/versions/20261028_01_rental_patrimony_customer.py").read_text()
    assert 'down_revision: str | None = "20261027_05"' in migration


def test_frontend_tabs_and_document_search():
    from pathlib import Path
    root = Path(__file__).parents[2]
    map_text = (root / 'web/src/features/inventory/InventoryPhysicalMap.tsx').read_text()
    for name in ['Estantes','Gavetas','Caixas','Galeias','Outros']:
        assert name in map_text
    ui = (root / 'web/src/features/customers/CustomerMaster.tsx').read_text()
    for term in ['"search"','"category"','"issue_date"','Limpar filtros']:
        assert term in ui
