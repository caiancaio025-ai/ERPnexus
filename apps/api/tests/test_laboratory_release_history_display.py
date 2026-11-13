from pathlib import Path


ROOT = Path(__file__).parents[1]
SCHEMAS = ROOT / "app" / "laboratory" / "schemas.py"
ROUTER = ROOT / "app" / "laboratory" / "router.py"


def test_status_history_exposes_release_snapshot_fields() -> None:
    source = SCHEMAS.read_text(encoding="utf-8")
    assert "release_event_id: int | None = None" in source
    assert "release_technician_id: int | None = None" in source
    assert "release_technician_name: str | None = None" in source
    assert "release_released_at: datetime | None = None" in source


def test_history_pairs_release_status_with_immutable_release_events() -> None:
    source = ROUTER.read_text(encoding="utf-8")
    assert "select(LaboratoryReleaseEvent)" in source
    assert "LaboratoryReleaseEvent.work_order_id == work_order_id" in source
    assert ".order_by(LaboratoryReleaseEvent.id)" in source
    assert 'history.new_status == "awaiting_pickup"' in source
    assert "release_technician_name=release_event.technician_name" in source
