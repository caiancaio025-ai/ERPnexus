"""Contrato do catálogo técnico e posições padronizadas de estoque V6."""
from pathlib import Path

import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable

from app.inventory.models import InventoryComponentCategory, InventoryComponentSubtype, InventoryItem
from app.inventory.schemas import CategoryInput, ContainerInput, ItemInput, ItemUpdate, SubtypeInput


def test_catalog_types_and_subtype_preserve_existing_item_links():
    assert InventoryComponentCategory.__table__.name == "inventory_component_categories"
    assert InventoryComponentSubtype.__table__.name == "inventory_component_subtypes"
    assert InventoryItem.__table__.c.subtype_id.foreign_keys
    sql = str(CreateTable(InventoryItem.__table__).compile(dialect=postgresql.dialect()))
    assert "subtype_id" in sql
    assert "serial_normalized" in sql


def test_category_and_subtype_payloads():
    assert CategoryInput(code="placa_disparo", name="Placa de disparo").code == "placa_disparo"
    assert SubtypeInput(category="capacitor", code="eletrolitico", name="Eletrolítico").name == "Eletrolítico"
    with pytest.raises(ValueError):
        CategoryInput(code="*", name="Inválido")
    assert ItemInput(company_code="universo_eletronica", name="Resistor 10k", mode="bulk", quantity=150, subtype_id=3).subtype_id == 3
    assert ItemUpdate(name="Resistor 10k", category="resistor", subtype_id=None).subtype_id is None


def test_estante_codes_are_one_to_five_with_fixed_shape():
    # O modelo mantém slots pré-existentes sem recodificar estoques antigos.
    source = (Path(__file__).parents[1] / "app/inventory/router.py").read_text(encoding="utf-8")
    assert 'kind.code == "estante"' in source
    assert 'payload.rows == 1 and payload.columns == 5' in source
    assert 'code = f"{box.code}{column}"' in source
    assert ContainerInput(area_id=1, type_id=1, code="A", name="Estante A", rows=1, columns=5).code == "A"


def test_ui_keeps_company_internal_but_not_visible_in_stock_form():
    ui = (Path(__file__).parents[2] / "web/src/features/inventory/InventoryDashboard.tsx").read_text(encoding="utf-8")
    assert "<label>Empresa<select" not in ui
    assert "stockMap.categories" in ui
    assert "stockMap.subtypes" in ui
    assert "Foto pronta para anexar ao salvar:" in ui
    assert "Tirar foto com a câmera" in ui
    assert "locationLabel(item.location_code)" in ui
