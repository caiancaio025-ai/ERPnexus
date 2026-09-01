from app.auth import access
from app.laboratory.schemas import WorkOrderSummary


def test_summary_exposes_approved_total():
    assert "approved_total" in WorkOrderSummary.model_fields


def test_summary_exposes_awaiting_approval_total():
    assert "awaiting_approval_total" in WorkOrderSummary.model_fields


def test_sensitive_value_permission_exists():
    fn = getattr(access, "user_can_view_sensitive_values", None)
    assert callable(fn), "Permissao monetaria especifica ainda nao existe."


def test_sensitive_values_are_gestao_only():
    fn = getattr(access, "user_can_view_sensitive_values", None)

    assert callable(fn), "Permissao monetaria especifica ainda nao existe."

    assert fn("gestao") is True
    assert fn("super_admin") is True

    assert fn("admin") is False
    assert fn("lab") is False
    assert fn("tecnico") is False
    assert fn("laboratorio") is False
    assert fn("compras") is False
    assert fn("financeiro") is False
    assert fn("consulta") is False


def test_finance_access_is_gestao_only():
    assert access.user_has_module(
        "gestao",
        [],
        access.MODULE_FINANCE,
    ) is True

    assert access.user_has_module(
        "super_admin",
        [],
        access.MODULE_FINANCE,
    ) is True

    assert access.user_has_module(
        "admin",
        [],
        access.MODULE_FINANCE,
    ) is False

    assert access.user_has_module(
        "financeiro",
        ["dashboard", "financeiro"],
        access.MODULE_FINANCE,
    ) is False
