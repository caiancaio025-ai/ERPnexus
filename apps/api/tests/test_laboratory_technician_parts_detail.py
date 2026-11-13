from pathlib import Path


ROOT = Path(__file__).parents[1]
SCHEMAS = ROOT / "app" / "laboratory" / "schemas.py"
REPORT = ROOT / "app" / "laboratory" / "production_report.py"


def test_report_exposes_purchased_part_details() -> None:
    schemas = SCHEMAS.read_text(encoding="utf-8")
    assert "class TechnicianProductionPartItem(BaseModel):" in schemas
    assert "item_name: str" in schemas
    assert "quantity: int" in schemas
    assert "unit_cost: Decimal" in schemas
    assert "subtotal: Decimal" in schemas
    assert "parts: list[TechnicianProductionPartItem] = []" in schemas


def test_part_detail_uses_same_canonical_cost_statuses_as_material_flow() -> None:
    source = REPORT.read_text(encoding="utf-8")
    assert "from app.purchasing.material_service import MATERIAL_COST_STATUSES" in source
    assert "MaterialRequest.status.in_(MATERIAL_COST_STATUSES)" in source
    assert "MaterialRequest.unit_cost.is_not(None)" in source


def test_part_subtotal_is_unit_cost_times_quantity() -> None:
    source = REPORT.read_text(encoding="utf-8")
    assert "subtotal=unit_cost * quantity" in source


def test_canonical_total_is_still_work_order_parts_cost() -> None:
    source = REPORT.read_text(encoding="utf-8")
    assert 'LaboratoryWorkOrder.parts_cost.label("canonical_parts_cost")' in source
    assert "parts_cost = _money(row.canonical_parts_cost)" in source


def test_part_values_are_not_returned_without_sensitive_permission() -> None:
    source = REPORT.read_text(encoding="utf-8")
    assert "if include_sensitive_values and work_order_ids:" in source
    assert "parts=parts_by_work_order.get(wo_id, []) if include_sensitive_values else []" in source
