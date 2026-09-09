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


def test_lab_transition_matrix_still_blocks_arbitrary_jump() -> None:
    assert can_transition("received", "delivered") is False
    assert can_transition("received", "in_analysis") is True


def test_backend_override_is_restricted_to_management_roles() -> None:
    source = LAB_ROUTER.read_text(encoding="utf-8")

    assert "def _can_override_work_order_status(user: User) -> bool:" in source
    assert 'return user.role.strip().lower() in {"super_admin", "admin", "gestao"}' in source
    assert "not _can_override_work_order_status(user)" in source
    assert "and not can_transition_status(work_order.status, payload.status)" in source


def test_frontend_management_roles_can_see_all_statuses() -> None:
    source = LAB_FRONTEND.read_text(encoding="utf-8")

    assert 'const canManageStatus = ["admin", "gestao", "super_admin"].includes(user.role);' in source
    assert "const visibleBusinessStatuses = canManageStatus" in source
    assert "? businessStatusOptions" in source
    assert "const visibleOperationalStatuses = canManageStatus" in source
    assert "? operationalStatusOptions" in source
    assert "canManageStatus={canManageStatus}" in source


def test_frontend_lab_still_uses_transition_matrix() -> None:
    source = LAB_FRONTEND.read_text(encoding="utf-8")

    assert "const validOperationalStatuses = new Set(operationalTransitions[detail.status] ?? []);" in source
    assert ": businessStatusOptions.filter((item) => validOperationalStatuses.has(item.value));" in source
    assert ": operationalStatusOptions.filter((item) => validOperationalStatuses.has(item.value));" in source


def test_cancelled_flag_tracks_current_status() -> None:
    source = LAB_ROUTER.read_text(encoding="utf-8")

    assert 'work_order.is_cancelled = payload.status == "cancelled"' in source


def test_completed_at_is_first_write_only() -> None:
    source = LAB_ROUTER.read_text(encoding="utf-8")

    assert 'if payload.status == "completed" and work_order.completed_at is None:' in source


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
        ("received", "delivered", False),
        ("received", "completed", False),
        ("received", "invoiced", False),
        ("cancelled", "received", True),
        ("invoiced", "warranty", True),
    ],
)
def test_operational_matrix_remains_governed_for_non_managers(
    current: str, target: str, expected: bool
) -> None:
    assert can_transition(current, target) is expected
