# pyright: basic
# O ReportLab não publica type stubs; em modo "strict" (ver .vscode/settings.json)
# qualquer objeto dele (Canvas, ParagraphStyle, Table...) aparece como "Unknown"
# em cascata. "basic" mantém as checagens úteis (nomes errados, tipos do NEXUS)
# só relaxando o que é impossível resolver sem stubs de terceiros.
from __future__ import annotations

from decimal import Decimal
from io import BytesIO
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
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.core.config import settings

if TYPE_CHECKING:
    from app.laboratory.models import LaboratoryEquipment, LaboratoryQuote, LaboratoryWorkOrder

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
    "solucoes_eletronica": ("Soluções Eletrônica Industrial", "", ""),
}
ADDRESS = "Av. Mascarenhas de Morais - Imbiribeira - Recife - PE"
PHONE = "81 98870-0589"


def money(value: Decimal) -> str:
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _boxed_paragraph(text: str, style: ParagraphStyle) -> Table:
    return Table(
        [[Paragraph((text or "—").replace("\n", "<br/>"), style)]],
        colWidths=[170 * mm],
        style=TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f5f7fa")),
                ("BOX", (0, 0), (-1, -1), 0.4, colors.HexColor("#d7dee7")),
                ("PADDING", (0, 0), (-1, -1), 8),
            ]
        ),
    )


def quote_pdf(
    work_order: LaboratoryWorkOrder,
    equipment: LaboratoryEquipment,
    quote: LaboratoryQuote,
) -> bytes:
    """Orçamento completo em A4. work_order: LaboratoryWorkOrder;
    equipment: LaboratoryEquipment (work_order.equipment); quote: LaboratoryQuote
    (com .items carregado)."""
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=16 * mm,
        leftMargin=16 * mm,
        topMargin=14 * mm,
        bottomMargin=14 * mm,
    )
    styles = getSampleStyleSheet()
    body = ParagraphStyle(
        "body",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=8.7,
        leading=12,
        textColor=colors.HexColor("#1f2937"),
    )
    small = ParagraphStyle("small", parent=body, fontSize=7.3, leading=9)
    title = ParagraphStyle(
        "title",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=18,
        textColor=colors.white,
    )
    section = ParagraphStyle(
        "section",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=11,
        textColor=colors.HexColor("#7092aa"),
        spaceBefore=8,
        spaceAfter=6,
    )
    company_name, cnpj, email = COMPANIES.get(
        work_order.company_code,
        COMPANIES["universo_eletronica"],
    )
    story = []

    header = Table(
        [
            [
                Paragraph(
                    (
                        f"<b>{company_name}</b><br/>"
                        f"<font size=8>CNPJ: {cnpj}<br/>{ADDRESS}<br/>"
                        f"Tel.: {PHONE} | {email}</font>"
                    ),
                    title,
                ),
                Paragraph(
                    (
                        f"<b>ORÇAMENTO PRÉVIO E<br/>ESTIMATIVO</b><br/>"
                        f"<font size=10>Nº {work_order.number}"
                        f" · Rev. {quote.revision:02d}<br/>"
                        "Emissão: "
                        f"{(quote.emitted_at or quote.updated_at).strftime('%d/%m/%Y')}"
                        "</font>"
                    ),
                    ParagraphStyle(
                        "hr",
                        parent=body,
                        textColor=colors.white,
                        alignment=TA_RIGHT,
                        fontSize=14,
                        leading=16,
                    ),
                ),
            ]
        ],
        colWidths=[115 * mm, 55 * mm],
        rowHeights=[34 * mm],
    )
    header.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#204f7b")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
            ]
        )
    )
    story.append(header)
    story.append(Spacer(1, 8))

    story.append(Paragraph("CLIENTE", section))
    story.append(
        Paragraph(
            f"<b>{work_order.customer_name}</b>",
            body,
        )
    )
    story.append(Spacer(1, 6))

    story.append(Paragraph("EQUIPAMENTO", section))
    equip_line = " · ".join(
        filter(None, [equipment.equipment_type, equipment.manufacturer, equipment.model])
    )
    story.append(Paragraph(equip_line or "—", body))
    if equipment.serial_number:
        story.append(Paragraph(f"Série: {equipment.serial_number}", small))
    story.append(Spacer(1, 6))

    story.append(Paragraph("DEFEITO INFORMADO PELO CLIENTE", section))
    story.append(_boxed_paragraph(work_order.reported_defect, body))
    story.append(Spacer(1, 6))

    story.append(Paragraph("DIAGNÓSTICO TÉCNICO / LAUDO", section))
    story.append(_boxed_paragraph(quote.technical_report, body))
    story.append(Spacer(1, 6))

    if quote.services_description:
        story.append(Paragraph("ESCOPO TÉCNICO", section))
        story.append(Paragraph(quote.services_description.replace("\n", "<br/>"), body))
        story.append(Spacer(1, 6))

    story.append(Paragraph("SERVIÇOS E COMPONENTES", section))
    rows = [["Descrição", "Qtd.", "Unitário", "Total"]]
    for item in quote.items:
        item_total = Decimal(item.quantity) * Decimal(item.unit_value)
        rows.append(
            [
                item.description,
                str(item.quantity),
                money(Decimal(item.unit_value)),
                money(item_total),
            ]
        )
    items_table = Table(rows, colWidths=[95 * mm, 20 * mm, 27 * mm, 28 * mm])
    items_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#204f7b")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8.4),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#d7dee7")),
                ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
                ("PADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    story.append(items_table)
    story.append(Spacer(1, 6))

    discount = (
        quote.subtotal * (quote.discount_value / 100)
        if quote.discount_type == "percent"
        else quote.discount_value if quote.discount_type == "amount" else Decimal(0)
    )
    summary = Table(
        [
            ["Subtotal", money(Decimal(quote.subtotal))],
            ["Desconto", money(Decimal(discount))],
            ["TOTAL", money(Decimal(quote.total))],
        ],
        colWidths=[140 * mm, 30 * mm],
    )
    summary.setStyle(
        TableStyle(
            [
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
                ("FONTNAME", (0, 2), (-1, 2), "Helvetica-Bold"),
                ("FONTSIZE", (0, 2), (-1, 2), 11),
                ("LINEABOVE", (0, 2), (-1, 2), 0.6, colors.HexColor("#204f7b")),
            ]
        )
    )
    story.append(summary)
    story.append(Spacer(1, 8))

    story.append(Paragraph("CONDIÇÕES COMERCIAIS", section))
    conditions = (
        f"Prazo de execução: {quote.delivery_days} dias · "
        f"Prazo de faturamento: {quote.billing_days} dias · "
        f"Garantia: {quote.warranty_months} meses · "
        f"Validade da proposta: {quote.validity_days} dias<br/>"
        f"Pagamento: {quote.payment_terms}<br/>{quote.return_condition}"
    )
    story.append(Paragraph(conditions, body))
    story.append(Spacer(1, 8))

    story.append(Paragraph(quote.consumer_clause, small))
    story.append(Spacer(1, 4))
    story.append(Paragraph(quote.supply_clause, small))
    story.append(Spacer(1, 4))
    story.append(Paragraph(quote.estimate_clause, small))
    story.append(Spacer(1, 14))

    approval = Table(
        [
            ["APROVAÇÃO DO CLIENTE"],
            ["Nome: _______________________________  Cargo: _____________________"],
            ["Data: ____/____/______  Assinatura: _______________________________"],
        ],
        colWidths=[170 * mm],
    )
    approval.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (0, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#204f7b")),
                ("PADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    story.append(approval)

    doc.build(story)
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
        height - 19.3 * mm,
        max_width=25.5 * mm,
        font="Helvetica",
        size=5.4,
        max_lines=3,
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
    bounds = widget.getBounds()
    size = 11.5 * mm
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
