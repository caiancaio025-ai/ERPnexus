from pathlib import Path


API_ROOT = Path(__file__).parents[1]
MIGRATION = API_ROOT / "migrations" / "versions" / "20261013_01_laboratory_release_events.py"
MODELS = API_ROOT / "app" / "laboratory" / "models.py"
ROUTER = API_ROOT / "app" / "laboratory" / "router.py"


def test_release_event_migration_is_chained_after_lab_final() -> None:
    source = MIGRATION.read_text(encoding="utf-8")
    assert 'revision: str = "20261013_01"' in source
    assert 'down_revision: str | None = "20261009_04"' in source
    assert '"laboratory_release_events"' in source


def test_release_event_model_preserves_technician_snapshot() -> None:
    source = MODELS.read_text(encoding="utf-8")
    assert "class LaboratoryReleaseEvent(Base):" in source
    assert 'ForeignKey("laboratory_work_orders.id", ondelete="CASCADE")' in source
    assert 'ForeignKey("laboratory_technicians.id", ondelete="SET NULL")' in source
    assert "technician_name: Mapped[str | None]" in source
    assert "released_at: Mapped[datetime]" in source
    assert "released_by_user_id: Mapped[int]" in source


def test_entering_awaiting_pickup_records_release_snapshot() -> None:
    source = ROUTER.read_text(encoding="utf-8")
    assert 'if payload.status == "awaiting_pickup":' in source
    assert "LaboratoryReleaseEvent(" in source
    assert "technician_id=technician.id if technician else None" in source
    assert "technician_name=technician.name if technician else None" in source
    assert "released_by_user_id=user.id" in source
    assert "previous_status=previous" in source


def test_status_remains_free_and_release_tracking_does_not_block_unassigned_os() -> None:
    source = ROUTER.read_text(encoding="utf-8")
    assert "if previous != payload.status:" in source
    assert "work_order.status = payload.status" in source
    assert "if work_order.assigned_technician_id is not None" in source
    assert "else None" in source


def test_historical_backfill_does_not_guess_technician() -> None:
    source = MIGRATION.read_text(encoding="utf-8")
    assert "WHERE history.new_status = 'awaiting_pickup'" in source
    assert "NULL,\n                NULL," in source
    assert "history.created_at" in source
    assert "history.user_id" in source
