"""Documento único para várias OS, com a identidade visual do orçamento atual."""
from datetime import datetime
from decimal import Decimal
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Image, KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.laboratory.quote_pdf import (
    BLUE, CYAN, DARK, DEFAULT_COMPANY, GEAR_LOGO, GEAR_WATERMARK, GRID,
    LIGHT, MUTED, SOFT_BLUE, _company_display_address, _info_card, _safe,
    _section_title, _text_panel, money,
)
from app.laboratory.grouped_quote_totals import line_total


def _date(value) -> str:
    try:
        return datetime.fromisoformat(str(value)).strftime("%d/%m/%Y")
    except (TypeError, ValueError):
        return str(value or "Não informada")


def grouped_quote_pdf(snapshot: dict) -> bytes:
    """Renderiza somente dados preparados; não lê ORM, arquivos mutáveis ou banco."""
    data = snapshot["quote"]
    company = {**DEFAULT_COMPANY, **snapshot["company"]}
    customer = snapshot["customer"]
    orders = data["work_orders"]
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
                            topMargin=14 * mm, bottomMargin=16 * mm,
                            title=f"Orçamento conjunto {data['code']} R{data['revision']:02d}")
    styles = getSampleStyleSheet()
    body = ParagraphStyle("group-body", parent=styles["BodyText"], fontName="Helvetica", fontSize=8.7, leading=11.8,
                          textColor=DARK, spaceBefore=0, spaceAfter=0)
    info = ParagraphStyle("group-info", parent=body, fontSize=8.3, leading=11.2)
    section = ParagraphStyle("group-section", parent=body, fontName="Helvetica-Bold", fontSize=10.2, leading=12, textColor=MUTED, keepWithNext=True)
    heading = ParagraphStyle("group-heading", parent=section, textColor=BLUE, fontSize=10.8, leading=13)
    white = ParagraphStyle("group-white", parent=body, textColor=colors.white)
    right = ParagraphStyle("group-right", parent=white, alignment=TA_RIGHT, fontName="Helvetica-Bold", leading=14)
    number = ParagraphStyle("group-number", parent=body, alignment=TA_RIGHT, fontSize=8.1, leading=10)
    clause = ParagraphStyle("group-clause", parent=body, fontSize=8.2, leading=10.7, textColor=colors.HexColor("#5c6d7d"))
    title = company.get("trade_name") or company.get("legal_name")
    company_text = Paragraph(
        f"<font name='Helvetica-Bold' size='14.8'>{_safe(title)}</font><br/>"
        f"<font name='Helvetica-Bold' size='9.8'>CNPJ: {_safe(company.get('document'))}</font><br/>"
        f"{_safe(_company_display_address(company))}<br/>"
        f"<b>Tel.: {_safe(company.get('phone'))}<br/>{_safe(company.get('email'))}</b>", white,
    )
    if GEAR_LOGO.exists():
        left = Table([[Image(str(GEAR_LOGO), width=27 * mm, height=27 * mm), company_text]], colWidths=[29 * mm, 68 * mm])
        left.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                                 ("RIGHTPADDING", (0, 0), (-1, -1), 3), ("TOPPADDING", (0, 0), (-1, -1), 0),
                                 ("BOTTOMPADDING", (0, 0), (-1, -1), 0)]))
    else:
        left = company_text
    right_text = Paragraph(
        "<font size='12'>ORÇAMENTO PRÉVIO<br/>E ESTIMATIVO</font><br/><br/>"
        f"<font size='11.6'>Nº {_safe(data['code'])}</font><br/>"
        f"Emissão: {_date(snapshot['issued_at'])}<br/>Validade: {data['validity_days']} dias", right,
    )
    header = Table([[left, right_text]], colWidths=[112 * mm, 62 * mm])
    header.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), BLUE), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                               ("TOPPADDING", (0, 0), (-1, -1), 14), ("BOTTOMPADDING", (0, 0), (-1, -1), 14),
                               ("LEFTPADDING", (0, 0), (-1, -1), 8), ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                               ("LINEBELOW", (0, 0), (-1, -1), 2.6, CYAN)]))
    banner = Table([[Paragraph("<b>CÓDIGO DE PRESTAÇÃO DE SERVIÇO</b>", info),
                     Paragraph(f"<b>{_safe(data['service_code'])}</b>", right)]], colWidths=[111 * mm, 63 * mm])
    banner.setStyle(TableStyle([("BACKGROUND", (0, 0), (0, 0), SOFT_BLUE), ("BACKGROUND", (1, 0), (1, 0), CYAN),
                               ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("TOPPADDING", (0, 0), (-1, -1), 7),
                               ("BOTTOMPADDING", (0, 0), (-1, -1), 7)]))
    cards = Table([[
        _info_card("DADOS DO CLIENTE", [("Cliente", customer.get("legal_name") or data["customer_name"]),
                                       ("CNPJ/CPF", customer.get("document")),
                                       ("Contato", customer.get("phone") or customer.get("email"))], info, section),
        _info_card("ORÇAMENTO CONJUNTO", [("Proposta", data["title"]), ("Equipamentos / OS", len(orders)),
                                         ("Revisão", f"{data['revision']:02d}")], info, section),
    ]], colWidths=[87 * mm, 87 * mm])
    cards.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                              ("RIGHTPADDING", (0, 0), (-1, -1), 4)]))
    story = [header, Spacer(1, 5), banner, Spacer(1, 7), cards, Spacer(1, 9),
             _section_title("DIAGNÓSTICO TÉCNICO / LAUDO", section), Spacer(1, 4),
             _text_panel(data["technical_report"], body), Spacer(1, 8),
             _section_title("SERVIÇO A REALIZAR", section), Spacer(1, 4),
             _text_panel(data["services_description"], body), Spacer(1, 9)]
    for order in orders:
        equipment = " ".join(str(order.get(key) or "").strip() for key in ("equipment_type", "manufacturer", "model")).strip()
        block = [
            _section_title(f"OS {order['number']} - SÉRIE {order.get('equipment_serial') or 'Não informada'}", heading),
            Spacer(1, 4), Paragraph(f"<b>Equipamento:</b> {_safe(equipment)}", body),
            Paragraph(f"<b>Entrada:</b> {_date(order['opened_at'])} &nbsp;&nbsp; <b>NF de entrada:</b> {_safe(order.get('entry_invoice'))}", body),
            Spacer(1, 5),
            Paragraph("<b>Defeito informado pelo cliente</b>", body), Spacer(1, 8),
            _text_panel(order["reported_defect"], body), Spacer(1, 7),
        ]
        rows = [["Serviços e componentes", "Qtd.", "Unitário", "Total"]]
        for item in data["items"]:
            if item["work_order_id"] == order["id"]:
                rows.append([Paragraph(_safe(item["description"]), body), Paragraph(f"{Decimal(item['quantity']):.3f}", number),
                             Paragraph(money(Decimal(item["unit_value"])), number),
                             Paragraph(money(line_total(Decimal(item["quantity"]), Decimal(item["unit_value"]))), number)])
        table = Table(rows, colWidths=[99 * mm, 18 * mm, 27 * mm, 30 * mm], repeatRows=1)
        table.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), BLUE), ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                                  ("BACKGROUND", (0, 1), (-1, -1), LIGHT), ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                                  ("FONTSIZE", (0, 0), (-1, -1), 8.3), ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
                                  ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LINEBELOW", (0, 0), (-1, -1), .35, GRID),
                                  ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
        per_order = Table([[Paragraph(f"Subtotal: <b>{money(Decimal(order['subtotal']))}</b> &nbsp; Desconto: <b>{money(Decimal(order['discount_amount']))}</b>", info),
                            Paragraph(f"<b>TOTAL OS: {money(Decimal(order['total']))}</b>", ParagraphStyle("os-total", parent=body, alignment=TA_RIGHT, textColor=BLUE))]],
                          colWidths=[112 * mm, 62 * mm])
        per_order.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), SOFT_BLUE), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                                      ("TOPPADDING", (0, 0), (-1, -1), 6), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
        block.extend([table, per_order, Spacer(1, 10)])
        # Uma OS curta passa inteira para a página seguinte quando necessário.
        # OS extensas continuam divisíveis; seu identificador não fica isolado
        # no rodapé enquanto o defeito e os valores começam em outra página.
        story.append(KeepTogether(block))
    summary = Table([
        ["Subtotal do conjunto", money(Decimal(data["subtotal"]))],
        ["Desconto do conjunto", money(Decimal(data["discount_amount"]))],
        ["TOTAL DO ORÇAMENTO", money(Decimal(data["total"]))],
    ], colWidths=[56 * mm, 38 * mm], hAlign="RIGHT")
    summary.setStyle(TableStyle([("ALIGN", (0, 0), (-1, -1), "RIGHT"), ("FONTNAME", (0, 0), (-1, -1), "Helvetica-Bold"),
                                ("FONTSIZE", (0, 0), (-1, -1), 9), ("TEXTCOLOR", (0, 0), (-1, -1), BLUE),
                                ("BACKGROUND", (0, 2), (-1, 2), SOFT_BLUE), ("LINEABOVE", (0, 2), (-1, 2), 1.2, BLUE),
                                ("LINEBELOW", (0, 2), (-1, 2), 1.2, BLUE), ("TOPPADDING", (0, 0), (-1, -1), 4),
                                ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
    story.extend([summary, Spacer(1, 10), _section_title("CONDIÇÕES COMERCIAIS", section), Spacer(1, 5)])
    conditions = Table([
        [Paragraph(f"<b>{label}</b>", info) for label in ("Prazo de execução", "Prazo de faturamento", "Garantia", "Validade")],
        [Paragraph(_safe(value), info) for value in (f"{data['delivery_days']} dias", data['billing_terms'] or f"{data['billing_days']} dias",
                                                    data['warranty_terms'] or f"{data['warranty_months']} meses", f"{data['validity_days']} dias")],
    ], colWidths=[48 * mm, 57 * mm, 44 * mm, 25 * mm])
    conditions.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), LIGHT), ("GRID", (0, 0), (-1, -1), .45, GRID),
                                   ("VALIGN", (0, 0), (-1, -1), "TOP"), ("TOPPADDING", (0, 0), (-1, -1), 4),
                                   ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
    story.extend([conditions, Spacer(1, 7), Paragraph(f"<b>Formas de pagamento:</b> {_safe(data['payment_terms'])}", body),
                  Paragraph(_safe(data['return_condition']), clause), Spacer(1, 10),
                  _section_title("TERMOS E CONDIÇÕES DA PROPOSTA", heading), Spacer(1, 6)])
    for title, key in (("Garantia legal / Código de Defesa do Consumidor", "consumer_clause"),
                       ("Prazo, insumos e fornecedores", "supply_clause"),
                       ("Natureza prévia e estimativa do orçamento", "estimate_clause")):
        story.append(Paragraph(f"<b>{_safe(title)}:</b> {_safe(data[key]).replace(chr(10), '<br/>')}", clause))
        if key != "estimate_clause":
            story.append(Spacer(1, 8))

    def page(canvas, document):
        canvas.saveState()
        if GEAR_WATERMARK.exists():
            canvas.drawImage(str(GEAR_WATERMARK), (A4[0] - 112 * mm) / 2, (A4[1] - 112 * mm) / 2 - 6 * mm,
                             width=112 * mm, height=112 * mm, preserveAspectRatio=True, mask="auto")
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(MUTED)
        canvas.drawString(18 * mm, 8 * mm, f"{data['code']} - Revisão {data['revision']:02d}")
        canvas.drawRightString(A4[0] - 18 * mm, 8 * mm, f"Página {document.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=page, onLaterPages=page)
    return buffer.getvalue()
