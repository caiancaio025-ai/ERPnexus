from __future__ import annotations

from io import BytesIO
from typing import Any
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

_NAVY = colors.HexColor("#0B1F33")
_BLUE = colors.HexColor("#1F78B4")
_CYAN = colors.HexColor("#42B9E8")
_INK = colors.HexColor("#223247")
_MUTED = colors.HexColor("#66788A")
_LINE = colors.HexColor("#D7E0E9")
_LIGHT = colors.HexColor("#F5F8FB")
_PALE_BLUE = colors.HexColor("#EAF4FB")
_WHITE = colors.white

_COMPANY_LABELS = {
    "universo_eletronica": "Universo Eletrônica",
    "universo_automacao": "Universo Automação",
    "solucoes_eletronica": "Soluções Eletrônicas",
}


def _money(value: float | int | None) -> str:
    amount = float(value or 0)
    return f"R$ {amount:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _safe(value: Any) -> str:
    return escape(str(value or ""))


def _multiline(value: Any) -> str:
    return _safe(value).replace("\n", "<br/>")


def _date(value: Any) -> str:
    if value is None:
        return "—"
    try:
        return value.strftime("%d/%m/%Y")
    except AttributeError:
        text = str(value)
        if len(text) >= 10 and text[4] == "-" and text[7] == "-":
            return f"{text[8:10]}/{text[5:7]}/{text[:4]}"
        return text


def _company_name(company: Any, company_code: str) -> str:
    if company is not None:
        return str(getattr(company, "trade_name", None) or getattr(company, "legal_name", None) or _COMPANY_LABELS.get(company_code, company_code))
    return _COMPANY_LABELS.get(company_code, company_code.replace("_", " ").title())


def _person_lines(entity: Any, *, fallback: str, company_code: str | None = None) -> list[str]:
    if entity is None:
        return [fallback]
    if company_code is not None:
        name = _company_name(entity, company_code)
    else:
        name = str(getattr(entity, "trade_name", None) or getattr(entity, "legal_name", None) or fallback)
    lines = [name]
    document = getattr(entity, "document", None)
    email = getattr(entity, "email", None)
    phone = getattr(entity, "phone", None)
    address = getattr(entity, "address", None)
    number = getattr(entity, "address_number", None)
    city = getattr(entity, "city", None)
    state = getattr(entity, "state", None)
    if document:
        lines.append(f"CNPJ/CPF: {document}")
    if email:
        lines.append(f"E-mail: {email}")
    if phone:
        lines.append(f"Telefone: {phone}")
    address_line = " ".join(str(value) for value in (address, number) if value)
    if address_line:
        lines.append(address_line)
    if city or state:
        lines.append(" / ".join(str(value) for value in (city, state) if value))
    return lines


def _footer(canvas: Canvas, doc: SimpleDocTemplate, *, display_number: str) -> None:
    canvas.saveState()
    width, _ = A4
    canvas.setStrokeColor(_LINE)
    canvas.setLineWidth(0.5)
    canvas.line(doc.leftMargin, 11 * mm, width - doc.rightMargin, 11 * mm)
    canvas.setFillColor(_MUTED)
    canvas.setFont("Helvetica", 7.2)
    canvas.drawString(doc.leftMargin, 6.5 * mm, f"NEXUS ENTERPRISE · {display_number}")
    canvas.drawRightString(width - doc.rightMargin, 6.5 * mm, f"Página {doc.page}")
    canvas.restoreState()


def commercial_quote_pdf(
    *,
    quote: Any,
    company: Any,
    customer: Any,
    items: list[Any],
    show_values: bool = True,
) -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=15 * mm,
        rightMargin=15 * mm,
        topMargin=14 * mm,
        bottomMargin=17 * mm,
        title=f"{quote.quote_number}",
        author="NEXUS Enterprise",
    )

    base = getSampleStyleSheet()
    brand = ParagraphStyle(
        "Brand",
        parent=base["BodyText"],
        fontName="Helvetica-Bold",
        fontSize=9.2,
        leading=11,
        textColor=_CYAN,
        letterSpacing=1.2,
    )
    doc_title = ParagraphStyle(
        "DocTitle",
        parent=base["Title"],
        fontName="Helvetica-Bold",
        fontSize=20,
        leading=23,
        alignment=TA_LEFT,
        textColor=_WHITE,
        spaceAfter=0,
    )
    header_meta = ParagraphStyle(
        "HeaderMeta",
        parent=base["BodyText"],
        fontName="Helvetica",
        fontSize=7.7,
        leading=11,
        alignment=TA_RIGHT,
        textColor=colors.HexColor("#DCEAF5"),
    )
    section = ParagraphStyle(
        "Section",
        parent=base["Heading3"],
        fontName="Helvetica-Bold",
        fontSize=10.2,
        leading=13,
        textColor=_NAVY,
        spaceBefore=2,
        spaceAfter=6,
    )
    body = ParagraphStyle(
        "Body",
        parent=base["BodyText"],
        fontName="Helvetica",
        fontSize=8.6,
        leading=12.2,
        textColor=_INK,
    )
    small = ParagraphStyle("Small", parent=body, fontSize=7.6, leading=10.6)
    tiny = ParagraphStyle("Tiny", parent=body, fontSize=7, leading=9.4, textColor=_MUTED)
    card_title = ParagraphStyle(
        "CardTitle",
        parent=small,
        fontName="Helvetica-Bold",
        fontSize=7.4,
        leading=9.5,
        textColor=_BLUE,
        spaceAfter=4,
    )
    item_header = ParagraphStyle(
        "ItemHeader",
        parent=small,
        fontName="Helvetica-Bold",
        textColor=_WHITE,
        alignment=TA_CENTER,
    )
    total_label = ParagraphStyle(
        "TotalLabel",
        parent=small,
        fontName="Helvetica-Bold",
        textColor=_MUTED,
        alignment=TA_RIGHT,
    )
    total_value = ParagraphStyle(
        "TotalValue",
        parent=base["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=15,
        leading=18,
        alignment=TA_RIGHT,
        textColor=_NAVY,
    )

    kind = {
        "sale": "Orçamento de Venda",
        "rental": "Orçamento de Locação",
        "preventive": "Orçamento de Manutenção Preventiva",
    }.get(quote.quote_type, "Orçamento Comercial")
    display_number = f"{quote.quote_number} · R{int(getattr(quote, 'revision', 1) or 1):02d}"
    company_name = _company_name(company, quote.company_code)

    header_left = [
        Paragraph("NEXUS ENTERPRISE", brand),
        Spacer(1, 2),
        Paragraph(kind, doc_title),
        Spacer(1, 3),
        Paragraph(_safe(getattr(quote, "title", None) or company_name), ParagraphStyle("HeaderSub", parent=small, textColor=colors.HexColor("#C2D7E7"))),
    ]
    header_right = Paragraph(
        "<b>" + _safe(display_number) + "</b><br/>"
        + f"Emissão: {_safe(_date(getattr(quote, 'issue_date', None)))}<br/>"
        + f"Validade: {_safe(_date(getattr(quote, 'valid_until', None)))}",
        header_meta,
    )
    header = Table([[header_left, header_right]], colWidths=[119 * mm, 56 * mm])
    header.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), _NAVY),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("LINEBELOW", (0, 0), (-1, -1), 2.2, _CYAN),
    ]))

    emitter_lines = _person_lines(company, fallback=company_name, company_code=quote.company_code)
    customer_lines = _person_lines(customer, fallback="Cliente removido")

    def info_card(title_text: str, lines: list[str]) -> list[Any]:
        content = [Paragraph(title_text.upper(), card_title)]
        if lines:
            content.append(Paragraph("<br/>".join(_safe(line) for line in lines), small))
        return content

    info = Table(
        [[info_card("Emitente", emitter_lines), info_card("Cliente", customer_lines)]],
        colWidths=[87.5 * mm, 87.5 * mm],
    )
    info.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), _LIGHT),
        ("BOX", (0, 0), (-1, -1), 0.55, _LINE),
        ("INNERGRID", (0, 0), (-1, -1), 0.45, _LINE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 9),
        ("RIGHTPADDING", (0, 0), (-1, -1), 9),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))

    story: list[Any] = [header, Spacer(1, 9), info, Spacer(1, 10)]

    if quote.intro_text:
        intro_box = Table([[Paragraph(_multiline(quote.intro_text), body)]], colWidths=[175 * mm])
        intro_box.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), _PALE_BLUE),
            ("BOX", (0, 0), (-1, -1), 0.45, colors.HexColor("#BFDCEB")),
            ("LEFTPADDING", (0, 0), (-1, -1), 9),
            ("RIGHTPADDING", (0, 0), (-1, -1), 9),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ]))
        story += [Paragraph("Apresentação", section), intro_box, Spacer(1, 10)]

    headers: list[Any] = [
        Paragraph("Descrição", item_header),
        Paragraph("Qtd.", item_header),
        Paragraph("Un.", item_header),
    ]
    if show_values:
        headers += [Paragraph("Valor unitário", item_header), Paragraph("Total", item_header)]
    data: list[list[Any]] = [headers]
    for item in items:
        spec = " · ".join(
            str(value)
            for value in [item.manufacturer, item.model, item.power, item.voltage, item.serial_number]
            if value
        )
        description_parts = [f"<b>{_safe(item.description)}</b>"]
        if spec:
            description_parts.append(f"<font color='#66788A' size='7'>{_safe(spec)}</font>")
        row: list[Any] = [
            Paragraph("<br/>".join(description_parts), small),
            Paragraph(f"{float(item.quantity):g}", small),
            Paragraph(_safe(item.unit), small),
        ]
        if show_values:
            row += [Paragraph(_money(item.unit_price), small), Paragraph(_money(item.line_total), small)]
        data.append(row)

    widths = [91 * mm, 16 * mm, 13 * mm] + ([27 * mm, 28 * mm] if show_values else [])
    items_table = Table(data, colWidths=widths, repeatRows=1, hAlign="LEFT")
    item_styles = [
        ("BACKGROUND", (0, 0), (-1, 0), _NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), _WHITE),
        ("GRID", (0, 0), (-1, -1), 0.35, _LINE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
    ]
    for row_index in range(1, len(data)):
        if row_index % 2 == 0:
            item_styles.append(("BACKGROUND", (0, row_index), (-1, row_index), _LIGHT))
    items_table.setStyle(TableStyle(item_styles))

    story += [Paragraph("Itens da proposta", section), items_table, Spacer(1, 7)]
    if show_values:
        total_box = Table(
            [[Paragraph("VALOR TOTAL DA PROPOSTA", total_label), Paragraph(_money(quote.total), total_value)]],
            colWidths=[112 * mm, 63 * mm],
        )
        total_box.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), _PALE_BLUE),
            ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#BFDCEB")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 9),
            ("RIGHTPADDING", (0, 0), (-1, -1), 9),
            ("TOPPADDING", (0, 0), (-1, -1), 7),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ]))
        story += [total_box, Spacer(1, 10)]

    blocks = [
        ("Escopo da preventiva", quote.preventive_scope if quote.quote_type == "preventive" else None),
        ("Condições de locação", quote.rental_terms if quote.quote_type == "rental" else None),
        ("Condições de entrega", quote.delivery_terms),
        ("Condições de pagamento", quote.payment_terms),
        ("Garantia", quote.warranty_terms),
        ("Exclusões", quote.exclusions),
        ("Observações", quote.notes),
    ]
    terms = [(heading, text) for heading, text in blocks if text]
    if terms:
        story.append(Paragraph("Condições comerciais", section))
        rows: list[list[Any]] = []
        for idx in range(0, len(terms), 2):
            cells: list[Any] = []
            for heading, text in terms[idx: idx + 2]:
                cells.append([
                    Paragraph(_safe(heading).upper(), card_title),
                    Paragraph(_multiline(text), small),
                ])
            if len(cells) == 1:
                cells.append("")
            rows.append(cells)
        terms_table = Table(rows, colWidths=[87.5 * mm, 87.5 * mm], hAlign="LEFT")
        terms_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), _WHITE),
            ("BOX", (0, 0), (-1, -1), 0.45, _LINE),
            ("INNERGRID", (0, 0), (-1, -1), 0.45, _LINE),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 7),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ]))
        story += [KeepTogether([terms_table]), Spacer(1, 7)]

    story.append(Paragraph(
        "Este documento foi gerado eletronicamente pelo NEXUS Enterprise. Confirme as condições acima antes da aprovação.",
        tiny,
    ))

    footer_cb = lambda canvas, current_doc: _footer(canvas, current_doc, display_number=display_number)
    doc.build(story, onFirstPage=footer_cb, onLaterPages=footer_cb)
    return buffer.getvalue()
