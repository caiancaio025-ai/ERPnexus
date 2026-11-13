from pathlib import Path

ROOT = Path(__file__).parents[1]
WEB = ROOT.parent / "web" / "src" / "features" / "inventory"


def test_dark_theme_and_simplified_locations():
    css = (WEB / "inventory.css").read_text(encoding="utf-8")
    dashboard = (WEB / "InventoryDashboard.tsx").read_text(encoding="utf-8")
    assert "#071522" in css and ".inv-locations-simple" in css
    assert "Estantes, caixas" not in dashboard  # painel antigo removido
    assert '"estante","caixa","gaveta"' in dashboard
    assert "Tipos, subtipos e formatos de componentes" in dashboard


def test_serialized_cannot_receive_additional_units_from_ui_or_api():
    ui = (WEB / "InventoryDashboard.tsx").read_text(encoding="utf-8")
    router = (ROOT / "app" / "inventory" / "router.py").read_text(encoding="utf-8")
    assert 'selected.mode==="bulk"&&<div className="inv-inline"' in ui
    assert 'if item.mode == "serialized":' in router
    assert 'Equipamento individual não admite novas entradas' in router


def test_auto_purchase_receives_only_when_physically_delivered():
    router = (ROOT / "app" / "purchasing" / "router.py").read_text(encoding="utf-8")
    assert 'purchase.status == "delivered"' in router
    assert 'payload.status == "received"' in router
    assert 'await receive_purchase(db, source="order"' in router
    assert 'await receive_purchase(db, source="request"' in router
    assert 'linked_source_id=' in router
