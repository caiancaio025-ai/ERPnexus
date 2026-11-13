from pathlib import Path

from app.laboratory.status_flow import WORK_ORDER_STATUSES, can_transition


API_ROOT = Path(__file__).parents[1]
REPO_APPS = Path(__file__).parents[2]
LAB_ROUTER = API_ROOT / "app" / "laboratory" / "router.py"
LAB_FRONTEND = REPO_APPS / "web" / "src" / "features" / "laboratory" / "LaboratoryDashboard.tsx"


def test_backend_keeps_eighteen_historical_status_codes() -> None:
    assert len(WORK_ORDER_STATUSES) == 18


def test_builtin_statuses_are_free_for_operational_use() -> None:
    assert can_transition("received", "in_analysis") is True
    assert can_transition("received", "invoiced") is True
    assert can_transition("cancelled", "approved") is True
    assert can_transition("invoiced", "received") is True


def test_backend_has_no_hierarchy_or_management_override_for_status_change() -> None:
    source = LAB_ROUTER.read_text(encoding="utf-8")
    assert "transition_allowed" not in source
    assert "status_override" not in source
    assert "Informe uma justificativa para o override de status." not in source
    assert "LaboratoryStatusHistory(" in source


def test_workflow_configuration_management_remains_restricted() -> None:
    source = LAB_ROUTER.read_text(encoding="utf-8")
    assert "def _can_override_work_order_status(user: User) -> bool:" in source
    assert 'return user.role.strip().lower() in {"super_admin", "admin", "gestao"}' in source


def test_frontend_exposes_all_active_statuses_without_transition_matrix() -> None:
    source = LAB_FRONTEND.read_text(encoding="utf-8")
    assert "const statusTransitions:" not in source
    assert "Override de Gestão" not in source
    assert "Status livre para a operação" in source


def test_location_is_visible_in_main_report_and_not_released_by_status() -> None:
    front = LAB_FRONTEND.read_text(encoding="utf-8")
    router = LAB_ROUTER.read_text(encoding="utf-8")
    assert "<th>Localização</th>" in front
    assert "lab-location-badge" in front
    assert "A localização é física e independente do status." in front
    assert "payload.status in TERMINAL_STATUSES and work_order.storage_location" not in router


def test_status_history_is_still_recorded() -> None:
    source = LAB_ROUTER.read_text(encoding="utf-8")
    assert "previous_status=previous" in source
    assert "new_status=payload.status" in source
    assert "note=payload.note" in source


def test_historical_status_codes_are_preserved_as_transition_targets() -> None:
    historical_targets = {"quote_sent", "completed", "delivered"}
    for current in WORK_ORDER_STATUSES:
        for target in historical_targets:
            assert can_transition(current, target) is True
