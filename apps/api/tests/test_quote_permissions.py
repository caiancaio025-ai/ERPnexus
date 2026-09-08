from pathlib import Path
import pytest

from app.auth.access import (
    user_can_create_quote,
    user_can_view_sensitive_values,
)


@pytest.mark.parametrize(
    ("role", "expected"),
    [
        ("gestao", True),
        ("super_admin", True),
        ("admin", True),
        ("lab", False),
        ("tecnico", False),
        ("consulta", False),
    ],
)
def test_quote_management_permission_matrix(role, expected):
    assert user_can_create_quote(role, None) is expected


def test_admin_quote_permission_does_not_grant_sensitive_values():
    assert user_can_create_quote("admin", None) is True
    assert user_can_view_sensitive_values("admin") is False

def test_laboratory_quote_listing_uses_quote_permission_for_values():
    source = (
        Path(__file__).parents[1]
        / "app"
        / "laboratory"
        / "router.py"
    ).read_text(encoding="utf-8")

    expected = (
        "include_values = "
        "user_can_create_quote(user.role, user.modules)"
    )

    assert expected in source, (
        "A listagem de orcamentos ainda usa permissao de valores sensiveis "
        "em vez da permissao funcional de orcamento."
    )


def test_laboratory_work_order_values_remain_sensitive_only():
    source = (
        Path(__file__).parents[1]
        / "app"
        / "laboratory"
        / "router.py"
    ).read_text(encoding="utf-8")

    assert (
        "include_sensitive_values="
        "user_can_view_sensitive_values(user.role)"
    ) in source

    assert (
        "parts_cost=work_order.parts_cost "
        "if include_sensitive_values else None"
    ) in source

def test_commercial_quote_operations_use_quote_permission():
    source = (
        Path(__file__).parents[1]
        / "app"
        / "commercial"
        / "router.py"
    ).read_text(encoding="utf-8")

    assert (
        "from app.auth.access import "
        "user_can_create_quote, user_can_view_sensitive_values"
    ) in source

    assert (
        "def _quote_allowed(user: User) -> bool:\n"
        "    return user_can_create_quote(user.role, user.modules)"
    ) in source

    assert "def _require_quote(user: User) -> None:" in source


def test_commercial_quote_output_uses_quote_permission_for_values():
    source = (
        Path(__file__).parents[1]
        / "app"
        / "commercial"
        / "router.py"
    ).read_text(encoding="utf-8")

    assert "show_values = _quote_allowed(user)" in source
    assert "show_values=_quote_allowed(user)" in source


def test_commercial_equipment_values_remain_sensitive_only():
    source = (
        Path(__file__).parents[1]
        / "app"
        / "commercial"
        / "router.py"
    ).read_text(encoding="utf-8")

    assert "def _money_allowed(user: User) -> bool:" in source
    assert "return user_can_view_sensitive_values(user.role)" in source

    assert "if _money_allowed(user): return rows" in source
    assert "_require_money(user)" in source

def test_laboratory_frontend_separates_quote_management_from_sensitive_values():
    source = (
        Path(__file__).parents[2]
        / "web"
        / "src"
        / "features"
        / "laboratory"
        / "LaboratoryDashboard.tsx"
    ).read_text(encoding="utf-8")

    assert (
        'const canViewValues = ["gestao", "super_admin"].includes(user.role);'
        in source
    )

    assert (
        'const canManageQuote = ["admin", "gestao", "super_admin"].includes(user.role);'
        in source
    )

    assert "canManageQuote={canManageQuote}" in source

    # Valores internos da O.S. continuam restritos ? Gest?o.
    assert '{canViewValues && <TabButton active={tab === "financial"}' in source
    assert "quotedValue={canViewValues ? detail.quoted_value : \"\"}" in source


def test_commercial_frontend_keeps_internal_equipment_money_gestao_only():
    source = (
        Path(__file__).parents[2]
        / "web"
        / "src"
        / "features"
        / "commercial"
        / "CommercialDashboard.tsx"
    ).read_text(encoding="utf-8")

    assert (
        'const canSeeMoney = (role:string) => '
        '["gestao","super_admin"].includes(role);'
        in source
    )

    # Criar or?amento comercial n?o pode depender de canSeeMoney.
    assert 'onClick={()=>setQuoteEditor({type:"sale",quote:null})}' in source
    assert 'onClick={()=>setQuoteEditor({type:"rental",quote:null})}' in source
    assert 'onClick={()=>setQuoteEditor({type:"preventive",quote:null})}' in source

