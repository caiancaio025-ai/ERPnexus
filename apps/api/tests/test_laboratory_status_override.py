from pathlib import Path

import pytest

from app.laboratory.status_flow import WORK_ORDER_STATUSES, can_transition


API_ROOT = Path(__file__).parents[1]
REPO_APPS = Path(__file__).parents[2]

LAB_ROUTER = API_ROOT / "app" / "laboratory" / "router.py"
LAB_FRONTEND = (
    REPO_APPS
    / "web"
    / "src"
    / "features"
    / "laboratory"
    / "LaboratoryDashboard.tsx"
)


def test_backend_has_exactly_eighteen_supported_statuses() -> None:
    assert len(WORK_ORDER_STATUSES) == 18


def test_builtin_main_statuses_have_no_transition_hierarchy() -> None:
    assert can_transition("received", "invoiced") is True
    assert can_transition("in_testing", "received") is True
    assert can_transition("cancelled", "approved") is True


def test_backend_no_longer_blocks_operational_users_by_transition_matrix() -> None:
    source = LAB_ROUTER.read_text(encoding="utf-8")

    assert "and not can_transition_status(work_order.status, payload.status)" not in source
    assert "Transição de {work_order.status} para {payload.status} não permitida." not in source
    assert "Status personalizados só podem ser aplicados pela ADM/Gestão." not in source
    assert "nao existe mais hierarquia" in source.lower()
    assert "payload.status in BUSINESS_STATUS_TARGETS" in source
    assert 'detail="Status do Laboratório inválido ou inativo."' in source


def test_workflow_configuration_management_remains_restricted() -> None:
    source = LAB_ROUTER.read_text(encoding="utf-8")

    assert "def _can_override_work_order_status(user: User) -> bool:" in source
    assert 'return user.role.strip().lower() in {"super_admin", "admin", "gestao"}' in source
    assert "A configuração de status do Laboratório é restrita à ADM/Gestão." in source


def test_frontend_all_laboratory_users_see_all_active_main_statuses() -> None:
    source = LAB_FRONTEND.read_text(encoding="utf-8")

    assert "const operationalTransitions" not in source
    assert "const validOperationalStatuses" not in source
    assert "primaryStatuses.filter" not in source
    assert "operationalStatusOptions.filter" not in source
    assert "const visibleOperationalStatuses = operationalStatusOptions;" in source
    assert (
        "const visibleBusinessStatuses = configuredBusinessStatuses.length ? configuredBusinessStatuses : businessStatusOptions;"
        in source
    )
    assert "qualquer status principal ativo, sem hierarquia de transição" in source


def test_cancelled_flag_tracks_current_status() -> None:
    source = LAB_ROUTER.read_text(encoding="utf-8")
    assert 'work_order.is_cancelled = payload.status == "cancelled"' in source


def test_completed_at_is_first_write_only() -> None:
    source = LAB_ROUTER.read_text(encoding="utf-8")
    assert 'if payload.status in {"completed", "awaiting_pickup"} and work_order.completed_at is None:' in source


def test_delivered_at_is_first_write_only() -> None:
    source = LAB_ROUTER.read_text(encoding="utf-8")
    assert 'if new_status == "delivered" and work_order.delivered_at is None:' in source


def test_status_history_is_still_recorded() -> None:
    source = LAB_ROUTER.read_text(encoding="utf-8")
    assert "LaboratoryStatusHistory(" in source
    assert "previous_status=previous" in source
    assert "new_status=payload.status" in source
    assert "note=payload.note" in source
    assert "user_id=user.id" in source


@pytest.mark.parametrize(
    ("current", "target", "expected"),
    [
        ("received", "invoiced", True),
        ("cancelled", "approved", True),
        ("invoiced", "received", True),
        ("in_repair", "warranty", True),
        ("awaiting_parts", "no_repair", True),
    ],
)
def test_operational_users_can_move_freely_between_main_statuses(
    current: str, target: str, expected: bool
) -> None:
    assert can_transition(current, target) is expected


def test_legacy_substatus_codes_are_never_transition_targets() -> None:
    legacy_targets = {"quote_sent", "completed", "delivered"}
    for current in WORK_ORDER_STATUSES:
        for target in legacy_targets:
            assert can_transition(current, target) is False
