from pathlib import Path
from types import SimpleNamespace

from app.commercial.quote_pdf import commercial_quote_pdf


API_ROOT = Path(__file__).parents[1]
WEB_ROOT = API_ROOT.parent / "web"


def test_laboratory_list_and_deep_link_expose_substatuses() -> None:
    source = (
        WEB_ROOT / "src" / "features" / "laboratory" / "LaboratoryDashboard.tsx"
    ).read_text(encoding="utf-8")

    assert "lab-substatus-mini" in source
    assert "substatusLabel(code, workflowOptions)" in source
    assert '"materials"' in source
    assert "detailTabFromQuery" in source


def test_purchasing_dashboard_surfaces_material_demands_and_notifications() -> None:
    source = (
        WEB_ROOT / "src" / "features" / "purchasing" / "PurchasingDashboard.tsx"
    ).read_text(encoding="utf-8")

    assert "/api/purchasing/material-requests" in source
    assert "/api/notifications?limit=20&unread_only=true" in source
    assert "Solicitações aguardando aprovação" in source
    assert "CENTRAL DE DEMANDAS" in source
    assert 'params.get("view")' in source
    assert "window.setInterval(refresh, 30000)" in source


def test_purchasing_can_open_approved_sale_in_commercial() -> None:
    purchasing = (
        WEB_ROOT / "src" / "features" / "purchasing" / "PurchasingDashboard.tsx"
    ).read_text(encoding="utf-8")
    commercial = (
        WEB_ROOT / "src" / "features" / "commercial" / "CommercialDashboard.tsx"
    ).read_text(encoding="utf-8")

    assert "notificationDestination" in purchasing
    assert '`/comercial?tab=orcamento&quote=${item.entity_id}`' in purchasing
    assert "Abrir orçamento no Comercial" in purchasing
    assert 'params.get("quote")' in commercial
    assert "deepLinkHandled" in commercial
    assert "setQuoteEditor({type:quote.quote_type,quote})" in commercial


def test_material_approval_notifies_laboratory() -> None:
    source = (API_ROOT / "app" / "purchasing" / "router.py").read_text(encoding="utf-8")

    assert 'category="material_request_approved"' in source
    assert 'modules={"laboratorio"}' in source
    assert 'target=f"/laboratorio?os={request.work_order_id}&aba=materials"' in source


def test_sale_approval_notifies_purchasing() -> None:
    source = (API_ROOT / "app" / "commercial" / "router.py").read_text(encoding="utf-8")

    assert 'quote.quote_type == "sale"' in source
    assert 'category="commercial_sale_approved"' in source
    assert 'modules={"compras"}' in source
    assert 'target=f"/comercial?tab=orcamento&quote={quote.id}"' in source


def test_quote_editor_has_all_issuers_and_approval_actions() -> None:
    source = (
        WEB_ROOT / "src" / "features" / "commercial" / "CommercialQuoteEditor.tsx"
    ).read_text(encoding="utf-8")

    assert "issuerLabels" in source
    assert "universo_eletronica" in source
    assert "universo_automacao" in source
    assert "solucoes_eletronica" in source
    assert "cadastro incompleto" in source
    assert "Aprovar venda" in source
    assert 'changeStatus("approved")' in source


def test_redesigned_commercial_pdf_renders_without_company_profile() -> None:
    quote = SimpleNamespace(
        quote_number="COM-000001",
        revision=1,
        quote_type="sale",
        company_code="universo_eletronica",
        issue_date=None,
        valid_until=None,
        title="Venda de inversor",
        intro_text="Proposta comercial.",
        preventive_scope=None,
        rental_terms=None,
        delivery_terms="Entrega em 10 dias.",
        payment_terms="30 dias.",
        warranty_terms="6 meses.",
        exclusions="Frete não incluso.",
        notes="Validade conforme proposta.",
        total=3333,
    )
    customer = SimpleNamespace(
        legal_name="Cliente Teste",
        trade_name=None,
        document="00.000.000/0001-00",
        email=None,
        phone=None,
        address=None,
        address_number=None,
        city="Recife",
        state="PE",
    )
    items = [
        SimpleNamespace(
            description="Inversor de frequência",
            manufacturer="WEG",
            model="CFW11",
            power="10 cv",
            voltage="380 V",
            serial_number="SN-001",
            quantity=1,
            unit="UN",
            unit_price=3333,
            line_total=3333,
        )
    ]

    pdf = commercial_quote_pdf(
        quote=quote,
        company=None,
        customer=customer,
        items=items,
        show_values=True,
    )

    assert pdf.startswith(b"%PDF")
    assert len(pdf) > 2500
