from pathlib import Path


ROOT = Path(__file__).parents[1]
MIGRATION = ROOT / "migrations" / "versions" / "20261013_02_commercial_patrimony.py"


def test_patrimony_migration_follows_current_head() -> None:
    source = MIGRATION.read_text(encoding="utf-8")
    assert 'revision: str = "20261013_02"' in source
    assert 'down_revision: str | None = "20261013_01"' in source


def test_patrimony_migration_blocks_non_individual_legacy_records() -> None:
    source = MIGRATION.read_text(encoding="utf-8")
    assert "quantity IS NULL OR quantity <> 1" in source
    assert "Individualize esses registros antes de aplicar esta migration." in source


def test_patrimony_migration_seeds_own_physical_map() -> None:
    source = MIGRATION.read_text(encoding="utf-8")
    assert "commercial_asset_areas" in source
    assert "commercial_asset_racks" in source
    assert "commercial_asset_locations" in source
    assert "PA" in source
    assert "PF" in source
