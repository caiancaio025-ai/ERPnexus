"""Regressão da numeração de gavetas e integração visual de Materiais."""
from pathlib import Path

from app.inventory.drawer_batch import missing_drawer_numbers


def test_creates_only_missing_drawers_and_keeps_padded_codes():
    missing = missing_drawer_numbers(["GAVETA-1", "GAVETA-002", "gaveta-445", "ESTANTE-A"])
    assert len(missing) == 490
    assert 1 not in missing and 2 not in missing and 445 not in missing
    assert 3 in missing and 493 in missing


def test_second_batch_is_idempotent():
    full = [f"GAVETA-{n}" for n in range(1, 494)]
    assert missing_drawer_numbers(full) == []


def test_existing_extra_numbers_do_not_affect_range():
    missing = missing_drawer_numbers(["GAVETA-494", "GAVETA-999", "GAVETA-3"])
    assert len(missing) == 492
    assert 3 not in missing


def test_rejects_excessive_ranges():
    import pytest
    with pytest.raises(ValueError):
        missing_drawer_numbers([], start=1, end=1000)


def test_material_actions_keep_existing_api_flows():
    root = Path(__file__).resolve().parents[2] / "web" / "src" / "features"
    materials = (root / "laboratory" / "components" / "MaterialsPanel.tsx").read_text(encoding="utf-8")
    use = (root / "inventory" / "InventoryUsePanel.tsx").read_text(encoding="utf-8")
    assert "activeAction === \"stock\"" in materials
    assert "activeAction === \"purchase\"" in materials
    assert "stockDestinationPayload(stockTarget)" in materials
    assert 'apiClient.post(`/inventory/items/${selected.id}/issue`' in use


def test_drawer_api_is_atomic_and_protected():
    root = Path(__file__).resolve().parents[1] / "app" / "inventory"
    route = (root / "router.py").read_text(encoding="utf-8")
    assert '@router.post("/containers/batch-drawers")' in route
    assert "Depends(require_module(\"estoque\"))" in route
    assert "await db.commit()" in route
    assert "await db.rollback()" in route
