from pathlib import Path

from app.laboratory.models import LaboratoryWorkflowOption, LaboratoryWorkOrderSubstatus


API_ROOT = Path(__file__).parents[1]
REPO_APPS = Path(__file__).parents[2]
ROUTER = API_ROOT / "app" / "laboratory" / "router.py"
SCHEMAS = API_ROOT / "app" / "laboratory" / "schemas.py"
MIGRATION = API_ROOT / "migrations" / "versions" / "20260914_01_laboratory_workflow_options.py"
FRONTEND = REPO_APPS / "web" / "src" / "features" / "laboratory" / "LaboratoryDashboard.tsx"


def test_workflow_models_have_history_safe_shape() -> None:
    workflow_columns = set(LaboratoryWorkflowOption.__table__.columns.keys())
    substatus_columns = set(LaboratoryWorkOrderSubstatus.__table__.columns.keys())

    assert {"kind", "code", "label", "sort_order", "is_active", "is_system"} <= workflow_columns
    assert {"work_order_id", "code", "is_active", "updated_by"} <= substatus_columns


def test_migration_seeds_requested_primary_statuses_and_substatuses() -> None:
    source = MIGRATION.read_text(encoding="utf-8")

    assert '("status", "in_analysis", "Em análise", 20, True)' in source
    assert '("status", "awaiting_pickup", "Liberado", 60, True)' in source
    assert '("substatus", "quote_sent", "Orçamento enviado", 10, True)' in source
    assert '("substatus", "awaiting_delivery", "Ag. entregar", 20, True)' in source
    assert '("substatus", "delivered", "Entregue", 30, True)' in source
    assert 'WHERE status = \'quote_sent\'' in source
    assert 'WHERE status = \'completed\'' in source
    assert 'WHERE status = \'delivered\'' in source


def test_frontend_removes_pronto_and_uses_substatus_checkboxes() -> None:
    source = FRONTEND.read_text(encoding="utf-8")

    assert 'in_analysis: "Em análise"' in source
    assert '{ value: "completed", label: "Pronto" }' not in source
    assert '{ value: "quote_sent", label: "Orçamento enviado" }' not in source
    assert '{ value: "delivered", label: "Entregue" }' not in source
    assert 'className="lab-substatus-grid"' in source
    assert 'detail.substatuses.includes(item.code)' in source


def test_workflow_settings_can_create_edit_deactivate_and_reactivate() -> None:
    source = FRONTEND.read_text(encoding="utf-8")

    assert 'Status e substatus' in source
    assert 'apiClient.post("/laboratory/workflow-options"' in source
    assert 'apiClient.put(`/laboratory/workflow-options/${editingWorkflowId}`' in source
    assert 'setWorkflowActive(item, false)' in source
    assert 'setWorkflowActive(item, true)' in source


def test_backend_blocks_legacy_substatus_targets_as_new_primary_statuses() -> None:
    source = ROUTER.read_text(encoding="utf-8")

    assert "if payload.status in LEGACY_SUBSTATUS_TARGETS:" in source
    assert '"Use a caixa de substatus correspondente na O.S."' in source
    assert '"/work-orders/{work_order_id}/substatuses/{substatus_code}"' in source
    assert 'action="substatus_changed"' in source


def test_quote_emission_marks_quote_sent_substatus() -> None:
    source = ROUTER.read_text(encoding="utf-8")

    assert 'code="quote_sent"' in source
    assert 'active=True' in source
    assert 'if not preview and quote.emitted_at is None:' in source


def test_status_schema_accepts_configurable_codes() -> None:
    source = SCHEMAS.read_text(encoding="utf-8")

    assert "LaboratoryStatus = str" in source
    assert "class WorkflowOptionCreate(BaseModel):" in source
    assert "class SubstatusToggleInput(BaseModel):" in source
