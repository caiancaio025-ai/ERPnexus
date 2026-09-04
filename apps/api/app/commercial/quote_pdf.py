from __future__ import annotations

from io import BytesIO
from typing import Any
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle


def _money(value: float | int | None) -> str:
    amount = float(value or 0)
    return f"R$ {amount:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _safe(value: Any) -> str:
    return escape(str(value or ""))


def _multiline(value: Any) -> str:
    return _safe(value).replace("\n", "<br/>")


def commercial_quote_pdf(*, quote: Any, company: Any, customer: Any, items: list[Any], show_values: bool = True) -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=16 * mm,
        rightMargin=16 * mm,
        topMargin=14 * mm,
        bottomMargin=14 * mm,
        title=f"{quote.quote_number}",
    )
    styles = getSampleStyleSheet()
    title = ParagraphStyle("Title2", parent=styles["Title"], fontSize=16, leading=20, alignment=TA_CENTER, textColor=colors.HexColor("#31518f"))
    section = ParagraphStyle("Section", parent=styles["Heading3"], fontSize=10, leading=13, textColor=colors.HexColor("#31518f"), spaceAfter=5)
    body = ParagraphStyle("Body2", parent=styles["BodyText"], fontSize=8.5, leading=12)
    small = ParagraphStyle("Small", parent=body, fontSize=7.5, leading=10)
    total_style = ParagraphStyle("Total", parent=styles["Heading2"], fontSize=12, alignment=TA_RIGHT, textColor=colors.HexColor("#31518f"))

    kind = {"sale": "Orçamento de Venda", "rental": "Orçamento de Locação", "preventive": "Orçamento de Manutenção Preventiva"}.get(quote.quote_type, "Orçamento Comercial")
    story: list[Any] = []
    display_number = f"{quote.quote_number} · R{int(getattr(quote, 'revision', 1) or 1):02d}"
    story.append(Table([[Paragraph("<b>NEXUS ENTERPRISE</b>", body), Paragraph(f"<b>{_safe(display_number)}</b>", body)]], colWidths=[120*mm, 42*mm], style=[("ALIGN", (1,0),(1,0), "RIGHT"), ("BOTTOMPADDING", (0,0),(-1,-1), 7), ("LINEBELOW", (0,0),(-1,-1), .8, colors.HexColor("#31518f"))]))
    story += [Spacer(1, 8), Paragraph(kind, title), Spacer(1, 10)]

    company_text = "<b>Dados da Empresa (Emitente)</b><br/>" + "<br/>".join(filter(None, [
        _safe(company.legal_name if company else quote.company_code),
        f"CNPJ/CPF: {_safe(company.document)}" if company and company.document else None,
        f"E-mail: {_safe(company.email)}" if company and company.email else None,
        f"Telefone: {_safe(company.phone)}" if company and company.phone else None,
        _safe(company.address) if company and company.address else None,
        f"{_safe(company.city)}/{_safe(company.state)}" if company and company.city and company.state else None,
    ]))
    customer_text = "<b>Dados do Cliente</b><br/>" + "<br/>".join(filter(None, [
        _safe(customer.legal_name) if customer else "Cliente removido",
        f"CNPJ/CPF: {_safe(customer.document)}" if customer and customer.document else None,
        f"E-mail: {_safe(customer.email)}" if customer and customer.email else None,
        f"Telefone: {_safe(customer.phone)}" if customer and customer.phone else None,
        " ".join(filter(None, [_safe(customer.address) if customer and customer.address else None, _safe(customer.address_number) if customer and customer.address_number else None])),
        f"{_safe(customer.city)}/{_safe(customer.state)}" if customer and customer.city and customer.state else None,
    ]))
    info = Table([[Paragraph(company_text, small), Paragraph(customer_text, small)]], colWidths=[81*mm,81*mm])
    info.setStyle(TableStyle([("BOX",(0,0),(-1,-1),.5,colors.HexColor("#ccd4df")),("INNERGRID",(0,0),(-1,-1),.35,colors.HexColor("#dde3eb")),("VALIGN",(0,0),(-1,-1),"TOP"),("PADDING",(0,0),(-1,-1),7)]))
    story += [info, Spacer(1, 10)]

    if quote.intro_text:
        story += [Paragraph("Apresentação", section), Paragraph(_multiline(quote.intro_text), body), Spacer(1, 8)]

    headers = ["Descrição", "Qtd.", "Un."]
    if show_values:
        headers += ["Valor unitário", "Total"]
    data: list[list[Any]] = [headers]
    for item in items:
        spec = " · ".join(_safe(value) for value in [item.manufacturer, item.model, item.power, item.voltage, item.serial_number] if value)
        description = _safe(item.description) + (f"<br/><font size='7'>{spec}</font>" if spec else "")
        row: list[Any] = [Paragraph(description, small), f"{float(item.quantity):g}", item.unit]
        if show_values:
            row += [_money(item.unit_price), _money(item.line_total)]
        data.append(row)
    widths = [93*mm, 16*mm, 14*mm] + ([22*mm, 24*mm] if show_values else [])
    table = Table(data, colWidths=widths, repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,0),colors.HexColor("#eef3f9")),("TEXTCOLOR",(0,0),(-1,0),colors.HexColor("#31518f")),("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),
        ("GRID",(0,0),(-1,-1),.35,colors.HexColor("#cbd5e1")),("VALIGN",(0,0),(-1,-1),"TOP"),("FONTSIZE",(0,0),(-1,-1),8),("PADDING",(0,0),(-1,-1),5),
        ("ALIGN",(1,1),(-1,-1),"RIGHT"),
    ]))
    story += [Paragraph("Detalhamento do orçamento", section), table, Spacer(1, 8)]
    if show_values:
        story += [Paragraph(f"Valor Total: {_money(quote.total)}", total_style), Spacer(1, 8)]

    blocks = [
        ("Escopo da preventiva", quote.preventive_scope if quote.quote_type == "preventive" else None),
        ("Condições de locação", quote.rental_terms if quote.quote_type == "rental" else None),
        ("Condições de entrega", quote.delivery_terms),
        ("Condições de pagamento", quote.payment_terms),
        ("Garantia", quote.warranty_terms),
        ("Exclusões", quote.exclusions),
        ("Detalhamento adicional / Observações", quote.notes),
    ]
    for heading, text in blocks:
        if text:
            story += [Paragraph(heading, section), Paragraph(_multiline(text), body), Spacer(1, 7)]

    doc.build(story)
    return buffer.getvalue()
