from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.auth.access import user_has_module
from app.laboratory.service import can_transition_status


# ---------------------------------------------------------------------------
# STATUS
# ---------------------------------------------------------------------------

def test_status_received_does_not_allow_arbitrary_business_jump():
    """
    O frontend nao deve oferecer uma transicao que o backend recusara.
    Este teste documenta a regra backend atualmente existente.
    """
    assert can_transition_status("received", "delivered") is False


def test_status_same_value_remains_idempotent():
    assert can_transition_status("in_analysis", "in_analysis") is True


# ---------------------------------------------------------------------------
# PERMISSAO MONETARIA
# ---------------------------------------------------------------------------

GESTAO_VALUE_ROLES = {"super_admin", "gestao"}


def can_view_sensitive_values(role: str) -> bool:
    return role.strip().lower() in GESTAO_VALUE_ROLES


@pytest.mark.parametrize(
    ("role", "expected"),
    [
        ("gestao", True),
        ("super_admin", True),
        ("admin", False),
        ("lab", False),
        ("tecnico", False),
        ("laboratorio", False),
        ("compras", False),
        ("financeiro", False),
        ("consulta", False),
    ],
)
def test_sensitive_values_are_restricted_to_gestao(role, expected):
    """
    Regra de negocio nova:
    informacoes monetarias operacionais somente Gestao/bootstrap.
    """
    assert can_view_sensitive_values(role) is expected


def test_finance_module_is_restricted_to_gestao():
    assert user_has_module(
        "gestao",
        [],
        "financeiro",
    ) is True

    assert user_has_module(
        "super_admin",
        [],
        "financeiro",
    ) is True

    assert user_has_module(
        "admin",
        [],
        "financeiro",
    ) is False

    assert user_has_module(
        "financeiro",
        ["dashboard", "financeiro"],
        "financeiro",
    ) is False


# ---------------------------------------------------------------------------
# TOTALIZACAO LABORATORIO
# ---------------------------------------------------------------------------

def total_for_status(rows, status, field):
    return sum(
        (
            Decimal(str(getattr(row, field) or 0))
            for row in rows
            if row.status == status
        ),
        Decimal("0"),
    )


def test_month_summary_approved_uses_approved_value():
    rows = [
        SimpleNamespace(status="approved", quoted_value=Decimal("1200"), approved_value=Decimal("1000")),
        SimpleNamespace(status="approved", quoted_value=Decimal("2300"), approved_value=Decimal("2300")),
        SimpleNamespace(status="awaiting_approval", quoted_value=Decimal("5000"), approved_value=None),
    ]

    assert total_for_status(rows, "approved", "approved_value") == Decimal("3300")


def test_month_summary_awaiting_approval_uses_quoted_value():
    rows = [
        SimpleNamespace(status="awaiting_approval", quoted_value=Decimal("1200"), approved_value=None),
        SimpleNamespace(status="awaiting_approval", quoted_value=Decimal("800"), approved_value=None),
        SimpleNamespace(status="approved", quoted_value=Decimal("9000"), approved_value=Decimal("9000")),
    ]

    assert total_for_status(rows, "awaiting_approval", "quoted_value") == Decimal("2000")


# ---------------------------------------------------------------------------
# CUSTO MATERIAL → OS
# ---------------------------------------------------------------------------

def material_total(unit_cost, quantity):
    return Decimal(str(unit_cost or 0)) * Decimal(str(quantity or 0))


def test_material_request_total_cost():
    assert material_total("325.50", 2) == Decimal("651.00")


def test_multiple_materials_can_compose_work_order_parts_cost():
    materials = [
        SimpleNamespace(unit_cost=Decimal("325.50"), quantity=2),
        SimpleNamespace(unit_cost=Decimal("100"), quantity=3),
        SimpleNamespace(unit_cost=None, quantity=1),
    ]

    total = sum(
        (material_total(item.unit_cost, item.quantity) for item in materials),
        Decimal("0"),
    )

    assert total == Decimal("951.00")
