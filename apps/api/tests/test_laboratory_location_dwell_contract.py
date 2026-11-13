from pathlib import Path


ROOT = Path(__file__).parents[1]
ROUTER = ROOT / "app" / "laboratory" / "router.py"
SCHEMAS = ROOT / "app" / "laboratory" / "schemas.py"


def test_location_map_exposes_dwell_alert_contract() -> None:
    schemas = SCHEMAS.read_text(encoding="utf-8")
    assert 'dwell_level: Literal["normal", "attention", "critical"] = "normal"' in schemas
    assert "location_duration_seconds: int = 0" in schemas
    assert "attention_work_orders: int" in schemas
    assert "critical_work_orders: int" in schemas


def test_location_map_uses_active_location_history_for_duration() -> None:
    source = ROUTER.read_text(encoding="utf-8")
    assert "LaboratoryLocationHistory.released_at.is_(None)" in source
    assert "location_dwell_seconds(assigned_at, now=now)" in source
    assert "location_dwell_level(duration_seconds)" in source
    assert "attention_work_orders" in source
    assert "critical_work_orders" in source
