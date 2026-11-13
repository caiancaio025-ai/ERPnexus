from pathlib import Path
from types import SimpleNamespace

from app.laboratory.service import group_work_orders_by_location

API_ROOT = Path(__file__).parents[1]
APPS_ROOT = API_ROOT.parent
MODELS = API_ROOT / "app" / "laboratory" / "models.py"
SERVICE = API_ROOT / "app" / "laboratory" / "service.py"
ROUTER = API_ROOT / "app" / "laboratory" / "router.py"
SCHEMAS = API_ROOT / "app" / "laboratory" / "schemas.py"
DASHBOARD = APPS_ROOT / "web" / "src" / "features" / "laboratory" / "LaboratoryDashboard.tsx"
MIGRATION = API_ROOT / "migrations" / "versions" / "20261009_01_laboratory_location_multi_occupancy.py"


def test_multiple_work_orders_can_share_same_location_in_grouping() -> None:
    first = SimpleNamespace(storage_location="A1", id=1)
    second = SimpleNamespace(storage_location="a1", id=2)
    grouped = group_work_orders_by_location([first, second])
    assert [item.id for item in grouped["A1"]] == [1, 2]


def test_model_and_migration_remove_unique_location_constraint() -> None:
    model = MODELS.read_text(encoding="utf-8")
    migration = MIGRATION.read_text(encoding="utf-8")
    assert 'storage_location: Mapped[str | None] = mapped_column(String(8), index=True)' in model
    assert 'storage_location: Mapped[str | None] = mapped_column(String(8), unique=True' not in model
    assert 'unique=False' in migration


def test_service_no_longer_blocks_duplicate_location() -> None:
    source = SERVICE.read_text(encoding="utf-8")
    assert 'já está ocupada por outra O.S.' not in source
    assert 'A posição pode ter várias O.S.' in source


def test_map_endpoint_imports_required_symbols_and_groups_occupants() -> None:
    source = ROUTER.read_text(encoding="utf-8")
    assert 'from sqlalchemy import func, or_, select' in source
    assert 'config = await _location_config_output(db)' in source
    assert 'active_locations' in source
    assert 'group_work_orders_by_location(located_orders)' in source
    assert 'occupants=occupants' in source


def test_map_schema_and_frontend_support_multiple_occupants() -> None:
    schemas = SCHEMAS.read_text(encoding="utf-8")
    dashboard = DASHBOARD.read_text(encoding="utf-8")
    assert 'class LaboratoryLocationOccupantOutput' in schemas
    assert 'occupants: list[LaboratoryLocationOccupantOutput]' in schemas
    assert 'slot.occupancy_count' in dashboard
    assert 'slot.occupants.map' in dashboard
    assert 'múltiplos equipamentos podem compartilhar a mesma localização' in dashboard


def test_position_suggestion_is_load_balanced_and_never_requires_uniqueness() -> None:
    source = SERVICE.read_text(encoding="utf-8")
    assert "func.count(LaboratoryWorkOrder.id)" in source
    assert "counts.get(location, 0)" in source
    dashboard = DASHBOARD.read_text(encoding="utf-8")
    assert "Sugerir melhor posição" in dashboard
    assert "Mais de uma O.S. pode compartilhar a mesma posição" in dashboard
