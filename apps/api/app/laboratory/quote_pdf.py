# pyright: basic
from __future__ import annotations

from decimal import Decimal
from html import escape
from io import BytesIO
from pathlib import Path
from typing import TYPE_CHECKING

from reportlab.graphics.barcode import qr
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import Image as PlatypusImage
from reportlab.platypus import KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.core.config import settings

if TYPE_CHECKING:
    from app.laboratory.models import (
        LaboratoryCustomer,
        LaboratoryEquipment,
        LaboratoryQuote,
        LaboratoryWorkOrder,
    )

COMPANIES = {
    "universo_eletronica": (
        "Universo Eletrônica Industrial",
        "32.157.227/0001-31",
        "universoeletronicaindustrial@gmail.com",
    ),
    "universo_automacao": (
        "Universo Automação Industrial",
        "51.196.568/0001-60",
        "universoautomacaoindustrial@gmail.com",
    ),
    "solucoes_eletronica": ("Soluções Eletrônicas Industriais", "51.196.568/0001-60", "comercial@sei.com.br"),
}
ADDRESS = "Av. Mascarenhas de Morais - Imbiribeira - Recife - PE"
PHONE = "81 98870-0589"
BLUE = colors.HexColor("#245681")
DARK = colors.HexColor("#344454")
MUTED = colors.HexColor("#5f8199")
CYAN = colors.HexColor("#10acd2")
LIGHT = colors.HexColor("#f6f8fa")
GRID = colors.HexColor("#d9e0e6")
SOFT_BLUE = colors.HexColor("#eef5fa")
ASSET_DIR = Path(__file__).with_name("assets")
GEAR_LOGO = ASSET_DIR / "gear_logo.png"
GEAR_WATERMARK = ASSET_DIR / "gear_watermark.png"


def money(value: Decimal) -> str:
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _safe(value: object | None, fallback: str = "Não informado") -> str:
    raw = str(value).strip() if value not in (None, "") else fallback
    return escape(raw)


def _section_title(text: str, style: ParagraphStyle) -> Table:
    return Table(
        [[Paragraph(_safe(text), style)]],
        colWidths=[174 * mm],
        style=TableStyle([
            ("LINEBELOW", (0, 0), (-1, -1), 0.45, GRID),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]),
    )


def _text_panel(text: object | None, style: ParagraphStyle, min_height: float = 13 * mm) -> Table:
    content = Paragraph(_safe(text).replace("\n", "<br/>"), style)
    return Table(
        [[content]],
        colWidths=[174 * mm],
        rowHeights=[min_height],
        style=TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), LIGHT),
            ("BOX", (0, 0), (-1, -1), 0.45, GRID),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 7),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ]),
    )


def _info_card(title: str, rows: list[tuple[str, object | None]], body: ParagraphStyle, title_style: ParagraphStyle) -> Table:
    flowables: list[object] = [Paragraph(_safe(title), title_style), Spacer(1, 2)]
    for label, value in rows:
        flowables.append(Paragraph(f"<b>{_safe(label, '')}:</b> {_safe(value)}", body))
        flowables.append(Spacer(1, 2.2))
    return Table(
        [[flowables]],
        colWidths=[82.5 * mm],
        rowHeights=[35 * mm],
        style=TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), LIGHT),
            ("BOX", (0, 0), (-1, -1), 0.45, GRID),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 9),
            ("RIGHTPADDING", (0, 0), (-1, -1), 9),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ]),
    )


def quote_pdf(
    work_order: LaboratoryWorkOrder,
    equipment: LaboratoryEquipment,
    quote: LaboratoryQuote,
    customer: LaboratoryCustomer | None = None,
) -> bytes:
    """Gera orçamento no padrão corporativo aprovado: 1ª página comercial/técnica e 2ª página de condições."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=18 * mm,
        leftMargin=18 * mm,
        topMargin=14 * mm,
        bottomMargin=13 * mm,
        title=f"Orçamento {work_order.number} R{quote.revision:02d}",
    )
    styles = getSampleStyleSheet()
    body = ParagraphStyle(
        "quote-body", parent=styles["BodyText"], fontName="Helvetica", fontSize=8.7,
        leading=11.8, textColor=DARK,
    )
    info_body = ParagraphStyle(
        "quote-info", parent=body, fontSize=8.3, leading=11.2,
    )
    company_style = ParagraphStyle(
        "company", parent=body, fontName="Helvetica-Bold", fontSize=17.5, leading=20,
        textColor=colors.white,
    )
    header_right = ParagraphStyle(
        "header-right", parent=body, fontName="Helvetica-Bold", fontSize=13.3, leading=16,
        textColor=colors.white, alignment=TA_RIGHT,
    )
    section = ParagraphStyle(
        "section", parent=body, fontName="Helvetica-Bold", fontSize=10.2, leading=12,
        textColor=MUTED,
    )
    card_title = ParagraphStyle(
        "card-title", parent=section, fontSize=9.4, leading=11,
    )
    clause = ParagraphStyle(
        "clause", parent=body, fontSize=8.2, leading=10.7, textColor=colors.HexColor("#5c6d7d"),
    )
    clause_heading = ParagraphStyle(
        "clause-heading", parent=section, fontSize=10.8, leading=13, textColor=BLUE,
    )

    company_name, cnpj, email = COMPANIES.get(work_order.company_code, COMPANIES["universo_eletronica"])
    emitted = quote.emitted_at or quote.updated_at
    service_code = _safe(getattr(quote, "service_code", None), "3312102 / 14.01")
    story: list[object] = []

    # Cabeçalho corporativo com símbolo da engrenagem isolado.
    company_text = Paragraph(
        f"{_safe(company_name)}<br/>"
        f"<font name='Helvetica' size='8.2'>CNPJ: {_safe(cnpj)}<br/>"
        f"{_safe(ADDRESS)}<br/>Tel.: {_safe(PHONE)} | {_safe(email)}</font>",
        company_style,
    )
    if GEAR_LOGO.exists():
        logo = PlatypusImage(str(GEAR_LOGO), width=27 * mm, height=27 * mm)
        left_header = Table([[logo, company_text]], colWidths=[31 * mm, 76 * mm])
        left_header.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (0, 0), 4),
            ("RIGHTPADDING", (1, 0), (1, 0), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ]))
    else:
        left_header = company_text

    # Revisão não é exibida no cabeçalho. Validade 0 continua visível.
    right_header = Paragraph(
        f"ORÇAMENTO PRÉVIO E<br/>ESTIMATIVO<br/>"
        f"<font name='Helvetica-Bold' size='8.8'>Nº {_safe(work_order.number)}</font><br/>"
        f"<font name='Helvetica' size='8.2'>Emissão: {emitted.strftime('%d/%m/%Y')}<br/>"
        f"Validade: {int(quote.validity_days)} dias</font>",
        header_right,
    )
    header = Table([[left_header, right_header]], colWidths=[111 * mm, 63 * mm], rowHeights=[48 * mm])
    header.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), BLUE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (0, 0), 8),
        ("RIGHTPADDING", (0, 0), (0, 0), 5),
        ("LEFTPADDING", (1, 0), (1, 0), 5),
        ("RIGHTPADDING", (1, 0), (1, 0), 8),
        ("LINEBELOW", (0, 0), (-1, -1), 2.6, CYAN),
    ]))
    story += [header, Spacer(1, 5)]

    # Destaque solicitado para o código de prestação de serviço.
    service_banner = Table(
        [[Paragraph("CÓDIGO DE PRESTAÇÃO DE SERVIÇO", ParagraphStyle(
            "svc-label", parent=body, fontName="Helvetica-Bold", fontSize=8.3, textColor=BLUE,
        )), Paragraph(service_code, ParagraphStyle(
            "svc-code", parent=body, fontName="Helvetica-Bold", fontSize=11, textColor=colors.white,
            alignment=TA_RIGHT,
        ))]],
        colWidths=[111 * mm, 63 * mm],
        rowHeights=[9 * mm],
    )
    service_banner.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (0, 0), SOFT_BLUE),
        ("BACKGROUND", (1, 0), (1, 0), CYAN),
        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#b8d7e5")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
    ]))
    story += [service_banner, Spacer(1, 7)]

    customer_rows = [
        ("Cliente", customer.legal_name if customer and customer.legal_name else work_order.customer_name),
        ("CNPJ/CPF", customer.document if customer else None),
        ("Contato", (customer.phone or customer.email) if customer else None),
    ]
    equip_power = equipment.power or getattr(equipment, "current", None)
    equipment_rows = [
        ("Equipamento", " ".join(str(v) for v in [equipment.equipment_type, equipment.manufacturer, equipment.model] if v)),
        ("Potência/Corrente", equip_power),
        ("Tensão", equipment.voltage),
        ("Data de Entrada", work_order.opened_at.strftime("%d/%m/%Y") if getattr(work_order, "opened_at", None) else None),
    ]
    cards = Table(
        [[_info_card("DADOS DO CLIENTE", customer_rows, info_body, card_title),
          _info_card("DADOS DO EQUIPAMENTO", equipment_rows, info_body, card_title)]],
        colWidths=[85 * mm, 85 * mm],
    )
    cards.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (0, 0), 0),
        ("RIGHTPADDING", (0, 0), (0, 0), 3.5),
        ("LEFTPADDING", (1, 0), (1, 0), 3.5),
        ("RIGHTPADDING", (1, 0), (1, 0), 0),
    ]))
    story += [cards, Spacer(1, 8)]

    story += [_section_title("DEFEITO INFORMADO PELO CLIENTE", section), Spacer(1, 3), _text_panel(work_order.reported_defect, body), Spacer(1, 7)]
    story += [_section_title("DIAGNÓSTICO TÉCNICO / LAUDO", section), Spacer(1, 3), _text_panel(quote.technical_report, body, 21 * mm), Spacer(1, 7)]
    story += [_section_title("SERVIÇO A REALIZAR", section), Spacer(1, 3), _text_panel(quote.services_description, body, 21 * mm), Spacer(1, 7)]

    story += [_section_title("SERVIÇOS E COMPONENTES", section), Spacer(1, 3)]
    rows: list[list[object]] = [["Descrição", "Qtd.", "Unitário", "Total"]]
    for item in quote.items:
        item_total = Decimal(item.quantity) * Decimal(item.unit_value)
        rows.append([
            Paragraph(_safe(item.description), body),
            f"{Decimal(item.quantity):.3f}",
            money(Decimal(item.unit_value)),
            money(item_total),
        ])
    items_table = Table(rows, colWidths=[99 * mm, 18 * mm, 27 * mm, 30 * mm], repeatRows=1)
    items_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), BLUE),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.3),
        ("BACKGROUND", (0, 1), (-1, -1), LIGHT),
        ("TEXTCOLOR", (0, 1), (-1, -1), DARK),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LINEBELOW", (0, 0), (-1, -1), 0.35, GRID),
    ]))
    story += [items_table, Spacer(1, 6)]

    discount = (
        Decimal(quote.subtotal) * (Decimal(quote.discount_value) / 100)
        if quote.discount_type == "percent"
        else Decimal(quote.discount_value)
        if quote.discount_type == "amount"
        else Decimal("0")
    )
    discount_label = f"Desconto ({Decimal(quote.discount_value):g}%)" if quote.discount_type == "percent" else "Desconto"
    summary = Table([
        ["Subtotal", money(Decimal(quote.subtotal))],
        [discount_label, f"- {money(discount)}" if discount > 0 else money(discount)],
        ["TOTAL DO ORÇAMENTO", money(Decimal(quote.total))],
    ], colWidths=[48 * mm, 35 * mm], hAlign="RIGHT")
    summary.setStyle(TableStyle([
        ("ALIGN", (0, 0), (-1, -1), "RIGHT"),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 1), 8.8),
        ("TEXTCOLOR", (0, 0), (-1, 0), DARK),
        ("TEXTCOLOR", (0, 1), (-1, 1), colors.HexColor("#c92f35") if discount > 0 else DARK),
        ("BACKGROUND", (0, 2), (-1, 2), SOFT_BLUE),
        ("TEXTCOLOR", (0, 2), (-1, 2), BLUE),
        ("FONTSIZE", (0, 2), (-1, 2), 10.5),
        ("LINEABOVE", (0, 2), (-1, 2), 1.2, BLUE),
        ("LINEBELOW", (0, 2), (-1, 2), 1.2, BLUE),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
    ]))
    story += [summary]

    # Página 2 - condições e cláusulas preservadas integralmente.
    story += [PageBreak(), _section_title("CONDIÇÕES COMERCIAIS", section), Spacer(1, 4)]
    conditions = Table([
        ["Prazo de execução", "Prazo de faturamento", "Garantia", "Validade"],
        [f"{quote.delivery_days} dias", f"{quote.billing_days} dias", f"{quote.warranty_months} meses", f"{quote.validity_days} dias"],
    ], colWidths=[57 * mm, 60 * mm, 32 * mm, 25 * mm])
    conditions.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f0f3f6")),
        ("BACKGROUND", (0, 1), (-1, 1), colors.white),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#506275")),
        ("TEXTCOLOR", (0, 1), (-1, 1), BLUE),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8.3),
        ("GRID", (0, 0), (-1, -1), 0.45, GRID),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
    ]))
    story += [conditions, Spacer(1, 7)]
    story += [
        Paragraph(f"<b>Formas de Pagamento:</b> {_safe(quote.payment_terms)}", body),
        Paragraph(f"<font color='#667788'>({_safe(quote.return_condition)})</font>", body),
        Spacer(1, 11),
        _section_title("TERMOS E CONDIÇÕES DA PROPOSTA", clause_heading),
        Spacer(1, 7),
    ]

    clauses = [
        ("Garantia legal / Código de Defesa do Consumidor", quote.consumer_clause),
        ("Prazo, insumos e fornecedores", quote.supply_clause),
        ("Natureza prévia e estimativa do orçamento", quote.estimate_clause),
    ]
    for heading, text in clauses:
        story += [
            Paragraph(f"<b>{_safe(heading)}:</b> {_safe(text).replace(chr(10), '<br/>')}", clause),
            Spacer(1, 8),
        ]

    def draw_watermark(canvas: Canvas, _doc: SimpleDocTemplate) -> None:
        if not GEAR_WATERMARK.exists():
            return
        width = 112 * mm
        height = 112 * mm
        page_width, page_height = A4
        canvas.saveState()
        canvas.drawImage(
            str(GEAR_WATERMARK),
            (page_width - width) / 2,
            (page_height - height) / 2 - 6 * mm,
            width=width,
            height=height,
            preserveAspectRatio=True,
            mask="auto",
        )
        canvas.restoreState()

    doc.build(story, onFirstPage=draw_watermark, onLaterPages=draw_watermark)
    return buffer.getvalue()

def _wrap_text(
    c: Canvas,
    text: str,
    x: float,
    y: float,
    max_width: float,
    font: str,
    size: float,
    max_lines: int,
) -> None:
    words = text.split()
    line = ""
    lines = []
    for word in words:
        trial = f"{line} {word}".strip()
        if stringWidth(trial, font, size) <= max_width:
            line = trial
        else:
            lines.append(line)
            line = word
        if len(lines) == max_lines:
            break
    if line and len(lines) < max_lines:
        lines.append(line)
    c.setFont(font, size)
    for i, ln in enumerate(lines):
        c.drawString(x, y - i * (size + 0.6), ln)


STATUS_LABELS_PT: dict[str, str] = {
    "received": "Recebido",
    "awaiting_analysis": "Aguardando análise",
    "in_analysis": "Em análise",
    "awaiting_quote": "Aguardando orçamento",
    "quote_sent": "Orçamento enviado",
    "awaiting_approval": "Aguardando aprovação",
    "approved": "Aprovado",
    "rejected": "Reprovado",
    "awaiting_parts": "Aguardando peças",
    "in_repair": "Em reparo",
    "in_testing": "Em testes",
    "completed": "Concluído",
    "awaiting_pickup": "Aguardando retirada",
    "delivered": "Entregue",
    "cancelled": "Cancelado",
    "no_repair": "Sem conserto",
}


def label_pdf(
    work_order: LaboratoryWorkOrder,
    equipment: LaboratoryEquipment,
    tracking_token: str,
) -> bytes:
    """Etiqueta 40 x 40 mm.

    work_order: LaboratoryWorkOrder (usa .number, .customer_name, .reported_defect, .status)
    equipment: LaboratoryEquipment (usa .equipment_type, .manufacturer, .model)
    tracking_token: work_order.tracking_token, usado na URL pública de rastreamento.
    """
    buffer = BytesIO()
    width, height = 40 * mm, 40 * mm
    c = Canvas(buffer, pagesize=(width, height))
    c.setLineWidth(0.6)
    c.rect(1.2 * mm, 1.2 * mm, width - 2.4 * mm, height - 2.4 * mm)

    c.setFont("Helvetica-Bold", 8.5)
    customer = work_order.customer_name[:22].upper()
    c.drawString(2.2 * mm, height - 5.5 * mm, customer)
    c.setFont("Helvetica-Bold", 7.5)
    c.drawRightString(width - 2.2 * mm, height - 5.5 * mm, work_order.number)
    c.line(2.2 * mm, height - 7 * mm, width - 2.2 * mm, height - 7 * mm)

    c.setFont("Helvetica-Bold", 6.4)
    equip = (equipment.equipment_type or "EQUIPAMENTO")[:30].upper()
    c.drawString(2.2 * mm, height - 10.5 * mm, equip)
    c.setFont("Helvetica", 5.6)
    specs = " · ".join(filter(None, [equipment.manufacturer, equipment.model]))[:36]
    c.drawString(2.2 * mm, height - 13.3 * mm, specs)

    defect = (work_order.reported_defect or "—")[:70]
    c.setFont("Helvetica-Bold", 5.2)
    c.drawString(2.2 * mm, height - 17 * mm, "DEFEITO:")
    _wrap_text(
        c,
        defect,
        2.2 * mm,
        height - 20.3 * mm,
        max_width=36 * mm,
        font="Helvetica",
        size=5.4,
        max_lines=1,
    )

    status_label = STATUS_LABELS_PT.get(work_order.status, work_order.status)
    c.setFont("Helvetica-Bold", 5.6)
    label_w = stringWidth(status_label.upper(), "Helvetica-Bold", 5.6) + 3 * mm
    c.setFillColor(colors.black)
    c.rect(2.2 * mm, 2.2 * mm, label_w, 3.6 * mm, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.drawString(2.2 * mm + 1.5 * mm, 3.1 * mm, status_label.upper())
    c.setFillColor(colors.black)

    tracking_url = f"{settings.tracking_base_url.rstrip('/')}/{tracking_token}"
    widget = qr.QrCodeWidget(tracking_url)
    widget.barLevel = "M"
    bounds = widget.getBounds()
    size = 17 * mm
    drawing = Drawing(
        size,
        size,
        transform=[
            size / (bounds[2] - bounds[0]),
            0,
            0,
            size / (bounds[3] - bounds[1]),
            0,
            0,
        ],
    )
    drawing.add(widget)
    drawing.drawOn(c, width - size - 2 * mm, 2.2 * mm)

    c.save()
    return buffer.getvalue()
