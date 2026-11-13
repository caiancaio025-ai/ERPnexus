from pathlib import Path


ROOT = Path(__file__).parents[1]
MODELS = ROOT / "app" / "commercial" / "models.py"
SCHEMAS = ROOT / "app" / "commercial" / "schemas.py"
ROUTER = ROOT / "app" / "commercial" / "router.py"
LABEL = ROOT / "app" / "commercial" / "label_pdf.py"


def test_commercial_equipment_is_individual_patimony() -> None:
    models = MODELS.read_text(encoding="utf-8")
    schemas = SCHEMAS.read_text(encoding="utf-8")
    assert 'CheckConstraint("quantity = 1"' in models
    assert "patrimony_code:" in models
    assert "manufacturer_serial:" in models
    assert "quantity: int = Field(default=1, ge=1, le=1)" in schemas


def test_patrimony_code_is_generated_before_first_flush() -> None:
    source = ROUTER.read_text(encoding="utf-8")
    create_equipment = source.split('async def create_equipment(', 1)[1].split('\n\n@router.put(', 1)[0]
    assert 'func.pg_get_serial_sequence(CommercialEquipment.__tablename__, "id")' in create_equipment
    assert 'patrimony_code=f"PAT-{equipment_id:06d}"' in create_equipment
    assert create_equipment.index('patrimony_code=f"PAT-{equipment_id:06d}"') < create_equipment.index('await db.flush()')
    assert "payload.quantity != 1" in create_equipment


def test_asset_location_has_own_tables_and_history() -> None:
    models = MODELS.read_text(encoding="utf-8")
    assert 'class CommercialAssetArea(Base):' in models
    assert 'class CommercialAssetRack(Base):' in models
    assert 'class CommercialAssetLocation(Base):' in models
    assert 'class CommercialAssetLocationHistory(Base):' in models
    assert 'CommercialAssetLocationHistory.released_at.is_(None)' in ROUTER.read_text(encoding="utf-8")


def test_label_uses_patrimony_serial_and_location() -> None:
    source = LABEL.read_text(encoding="utf-8")
    assert 'equipment.patrimony_code' in source
    assert 'equipment.manufacturer_serial' in source
    assert 'equipment.location' in source
    assert 'QrCodeWidget(patrimony)' in source


def test_asset_map_endpoints_exist() -> None:
    source = ROUTER.read_text(encoding="utf-8")
    assert '@router.get("/asset-locations", response_model=CommercialAssetLocationConfig)' in source
    assert '@router.get("/asset-map", response_model=CommercialAssetMapOutput)' in source
    assert '"/equipment/{equipment_id}/location-history"' in source
    assert '@router.put("/equipment/{equipment_id}/location"' in source
