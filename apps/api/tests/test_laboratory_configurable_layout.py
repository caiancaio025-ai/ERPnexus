from pathlib import Path

from app.laboratory.schemas import LaboratoryRackInput, LaboratoryRackUpdate


API_ROOT = Path(__file__).parents[1]
WEB_ROOT = API_ROOT.parent / "web"
MIGRATION = API_ROOT / "migrations" / "versions" / "20261009_03_laboratory_rack_layout.py"
MODELS = API_ROOT / "app" / "laboratory" / "models.py"
SCHEMAS = API_ROOT / "app" / "laboratory" / "schemas.py"
ROUTER = API_ROOT / "app" / "laboratory" / "router.py"
DASHBOARD = WEB_ROOT / "src" / "features" / "laboratory" / "LaboratoryDashboard.tsx"
PANEL = WEB_ROOT / "src" / "features" / "laboratory" / "components" / "ConfigMasterPanel.tsx"
CSS = WEB_ROOT / "src" / "features" / "laboratory" / "laboratory.css"
TYPES = WEB_ROOT / "src" / "features" / "laboratory" / "types.ts"


def test_rack_layout_migration_is_chained_and_preserves_real_operation_drawing() -> None:
    source = MIGRATION.read_text(encoding="utf-8")
    assert 'revision: str = "20261009_03"' in source
    assert 'down_revision: str | None = "20261009_02"' in source
    assert '"layout_row"' in source
    assert '"layout_column"' in source
    assert '"layout_span"' in source
    assert '"E1": (1, 2, 1)' in source
    assert '"E5": (2, 1, 1)' in source
    assert '"E2": (2, 2, 1)' in source
    assert '"E6": (3, 1, 1)' in source
    assert '"E3": (3, 2, 1)' in source
    assert '"E4": (4, 2, 1)' in source


def test_rack_schema_accepts_configurable_map_position() -> None:
    created = LaboratoryRackInput(
        area_id=1,
        code="E7",
        name="Estante 7 - Entrada",
        position_prefix="G",
        rows=3,
        columns=2,
        layout_row=4,
        layout_column=1,
        layout_span=1,
    )
    assert created.layout_row == 4
    assert created.layout_column == 1
    assert created.layout_span == 1

    updated = LaboratoryRackUpdate(
        name="Estante 7 - Entrada",
        layout_row=5,
        layout_column=2,
        layout_span=2,
        is_active=True,
    )
    assert (updated.layout_row, updated.layout_column, updated.layout_span) == (5, 2, 2)


def test_rack_model_and_map_api_expose_visual_placement() -> None:
    model = MODELS.read_text(encoding="utf-8")
    schema = SCHEMAS.read_text(encoding="utf-8")
    router = ROUTER.read_text(encoding="utf-8")
    assert "layout_row: Mapped[int]" in model
    assert "layout_column: Mapped[int]" in model
    assert "layout_span: Mapped[int]" in model
    assert "rack_layout_row: int = 1" in schema
    assert "rack_layout_column: int = 1" in schema
    assert "rack_layout_span: int = 1" in schema
    assert "rack_layout_row=rack.layout_row if rack else 1" in router


def test_config_master_allows_selecting_where_new_rack_is_drawn() -> None:
    source = PANEL.read_text(encoding="utf-8")
    assert "Linha no mapa" in source
    assert "Coluna no mapa" in source
    assert "Largura no mapa" in source
    assert "layout_row: Number(rackForm.layout_row)" in source
    assert "layout_column: Number(rackForm.layout_column)" in source
    assert "layout_span: Number(rackForm.layout_span)" in source


def test_map_uses_persisted_rack_coordinates_not_hardcoded_component_positions() -> None:
    source = DASHBOARD.read_text(encoding="utf-8")
    assert "gridRow: first.rack_layout_row" in source
    assert "gridColumn: `${first.rack_layout_column} / span ${first.rack_layout_span}`" in source
    assert "rack_layout_column + slot.rack_layout_span - 1" in source


def test_location_input_supports_both_typing_and_suggestions() -> None:
    source = DASHBOARD.read_text(encoding="utf-8")
    assert "const listId = useId()" in source
    assert "list={listId}" in source
    assert "<datalist id={listId}>" in source
    assert 'placeholder="Digite A2, LAB, MEC... ou selecione"' in source
    assert "Código ainda não corresponde a uma localização ativa cadastrada." in source


def test_visual_racks_have_industrial_rack_treatment() -> None:
    css = CSS.read_text(encoding="utf-8")
    dashboard = DASHBOARD.read_text(encoding="utf-8")
    assert "lab-rack-visual-shell" in dashboard
    assert "lab-rack-top-beam" in dashboard
    assert ".lab-rack-visual-shell::before" in css
    assert ".lab-rack-top-beam" in css
    assert "repeating-linear-gradient" in css


def test_frontend_types_include_rack_layout_contract() -> None:
    source = TYPES.read_text(encoding="utf-8")
    assert "layout_row: number; layout_column: number; layout_span: number;" in source
    assert "rack_layout_row: number;" in source
    assert "rack_layout_column: number;" in source
    assert "rack_layout_span: number;" in source


def test_layout_collision_guard_prevents_overlapping_racks() -> None:
    source = ROUTER.read_text(encoding="utf-8")
    assert "async def _ensure_rack_layout_available" in source
    assert "A posição visual escolhida conflita com a estante" in source
    assert "other_end = row.layout_column + row.layout_span - 1" in source
    assert "exclude_rack_id=rack.id" in source
