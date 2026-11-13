from pathlib import Path

from app.laboratory.service import (
    LAB_PHYSICAL_LOCATIONS,
    LAB_RACKS,
    LAB_RACK_SLOT_COUNT,
)


API_ROOT = Path(__file__).parents[1]
APPS_ROOT = API_ROOT.parent
ROUTER = API_ROOT / "app" / "laboratory" / "router.py"
DASHBOARD = APPS_ROOT / "web" / "src" / "features" / "laboratory" / "LaboratoryDashboard.tsx"
CSS = APPS_ROOT / "web" / "src" / "features" / "laboratory" / "laboratory.css"


def test_physical_racks_follow_real_lab_mapping() -> None:
    assert LAB_RACKS == (
        ("E1", "A"),
        ("E2", "B"),
        ("E3", "C"),
        ("E4", "D"),
        ("E5", "E"),
        ("E6", "F"),
    )
    assert LAB_RACK_SLOT_COUNT == 6
    assert LAB_PHYSICAL_LOCATIONS == (
        "A1", "A2", "A3", "A4", "A5", "A6",
        "B1", "B2", "B3", "B4", "B5", "B6",
        "C1", "C2", "C3", "C4", "C5", "C6",
        "D1", "D2", "D3", "D4", "D5", "D6",
        "E1", "E2", "E3", "E4", "E5", "E6",
        "F1", "F2", "F3", "F4", "F5", "F6",
    )


def test_location_map_api_contract_exists() -> None:
    source = ROUTER.read_text(encoding="utf-8")
    assert '@router.get("/locations/map", response_model=LaboratoryLocationMapOutput)' in source
    assert "config = await _location_config_output(db)" in source
    assert "total_positions=len(slots)" in source
    assert "work_orders_without_location=without_location" in source
    assert "urgent_positions=urgent_positions" in source


def test_frontend_has_visual_physical_map() -> None:
    source = DASHBOARD.read_text(encoding="utf-8")
    assert "Mapa de localizações" in source
    assert "RASTREABILIDADE FÍSICA" in source
    assert "lab-area-tabs" in source
    assert "lab-configurable-racks" in source
    assert "slot.area_code" in source
    assert "onOpenLocation(slot.location)" in source


def test_location_map_has_operational_filters_and_pseudo_3d_css() -> None:
    source = DASHBOARD.read_text(encoding="utf-8")
    css = CSS.read_text(encoding="utf-8")
    assert 'filter === "occupied"' in source
    assert 'filter === "free"' in source
    assert 'filter === "urgent"' in source
    assert "Sem localização" in source
    assert ".lab-configurable-map" in css
    assert ".lab-area-location-card" in css
    assert ".lab-rack-slot.urgent" in css


def test_location_map_uses_denormalized_customer_name_instead_of_missing_relationship() -> None:
    source = ROUTER.read_text(encoding="utf-8")
    assert "work_order.customer.legal_name" not in source
    assert 'customer_name=work_order.customer_name or "Sem cliente"' in source


def test_location_click_opens_direct_preview_without_navigating_to_map_first() -> None:
    source = DASHBOARD.read_text(encoding="utf-8")
    assert "openLocationPreview(order.storage_location!)" in source
    assert "LocationPreviewModal" in source
    assert "Mostrar esta posição no mapa" in source
    assert "Abrir mapa completo" in source
    assert 'item.location === location ? "focused" : ""' in source


def test_location_map_frontend_refreshes_snapshot_after_mutations_and_on_preview() -> None:
    source = DASHBOARD.read_text(encoding="utf-8")
    assert "const data = await loadLocationMap({ silent: true });" in source
    assert "window.setInterval" in source
    assert "document.visibilityState" in source
    assert "10000" in source
    assert "locationMapUpdatedAt" in source


def test_work_order_location_is_validated_against_config_master() -> None:
    schemas = (API_ROOT / "app" / "laboratory" / "schemas.py").read_text(encoding="utf-8")
    service = (API_ROOT / "app" / "laboratory" / "service.py").read_text(encoding="utf-8")
    assert "O código da localização deve ter no máximo 8 caracteres." in schemas
    assert "Localização física inexistente ou inativa" in service
    assert "LaboratoryLocation.code == normalized" in service


def test_out_of_map_legacy_locations_are_counted_for_attention() -> None:
    source = ROUTER.read_text(encoding="utf-8")
    assert "~LaboratoryWorkOrder.storage_location.in_(valid_codes)" in source
