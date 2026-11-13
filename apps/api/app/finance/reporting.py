from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import Decimal
from io import BytesIO
from typing import Iterable, Sequence
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.finance.schemas import FinanceSummary


COMPANY_LABELS = {
    "universo_eletronica": "Universo Eletrônica",
    "universo_automacao": "Universo Automação",
    "solucoes_eletronica": "Soluções Eletrônica",
}

DATE_BASIS_LABELS = {
    "posting": "Competência / lançamento",
    "issue": "Emissão",
    "due": "Vencimento",
    "settlement": "Baixa",
}

STATUS_LABELS = {
    "pending": "Pendente",
    "paid": "Pago",
    "received": "Recebido",
    "cancelled": "Cancelado",
}

ENTRY_TYPE_LABELS = {"income": "Receita", "expense": "Saída"}


def company_report_label(company_code: str | None, consolidated: bool) -> str:
    if consolidated:
        return "Grupo consolidado"
    if company_code:
        return COMPANY_LABELS.get(company_code, company_code)
    return "Grupo consolidado"


def finance_report_filename(extension: str, company_code: str | None, consolidated: bool, period_end: date) -> str:
    company = "consolidado" if consolidated or not company_code else company_code
    safe_extension = extension.lower().lstrip(".")
    return f"financeiro_{company}_{period_end.isoformat()}.{safe_extension}"


def _money(value: float | Decimal | int | None) -> str:
    amount = Decimal(str(value or 0)).quantize(Decimal("0.01"))
    integer, cents = f"{abs(amount):.2f}".split(".")
    groups: list[str] = []
    while integer:
        groups.insert(0, integer[-3:])
        integer = integer[:-3]
    formatted = ".".join(groups) + "," + cents
    prefix = "-" if amount < 0 else ""
    return f"{prefix}R$ {formatted}"


def _entry_value(entry: object, name: str, default=None):
    return getattr(entry, name, default)


def _period_label(summary: FinanceSummary) -> str:
    return f"{summary.period_start.strftime('%d/%m/%Y')} a {summary.period_end.strftime('%d/%m/%Y')}"


def _basis_label(summary: FinanceSummary) -> str:
    return DATE_BASIS_LABELS.get(summary.date_basis, summary.date_basis)


def _percent_change(current: float | Decimal | int, previous: float | Decimal | int) -> float | None:
    current_value = Decimal(str(current or 0))
    previous_value = Decimal(str(previous or 0))
    if previous_value == 0:
        return None if current_value == 0 else 100.0
    return float(((current_value - previous_value) / abs(previous_value)) * Decimal("100"))


def _rank_entries(
    entries: Sequence[object],
    *,
    entry_type: str,
    only_pending: bool = False,
    limit: int = 5,
) -> list[tuple[str, float]]:
    totals: dict[str, Decimal] = defaultdict(lambda: Decimal("0"))
    for entry in entries:
        if str(_entry_value(entry, "entry_type", "")) != entry_type:
            continue
        if only_pending and str(_entry_value(entry, "status", "")) != "pending":
            continue
        name = str(_entry_value(entry, "counterparty_name", "")).strip() or "Não informado"
        totals[name] += Decimal(str(_entry_value(entry, "amount", 0) or 0))
    ranked = sorted(totals.items(), key=lambda item: item[1], reverse=True)[:limit]
    return [(name, float(value)) for name, value in ranked]


def _due_30_amounts(summary: FinanceSummary) -> tuple[float, float, int]:
    wanted = {"due_today", "due_1_7", "due_8_30"}
    income = 0.0
    expense = 0.0
    count = 0
    for bucket in summary.aging:
        if bucket.key in wanted:
            income += bucket.income
            expense += bucket.expense
            count += bucket.count
    return income, expense, count


def _executive_insights(summary: FinanceSummary, entries: Sequence[object]) -> dict[str, object]:
    top_income = _rank_entries(entries, entry_type="income")
    top_expense = _rank_entries(entries, entry_type="expense")
    pending_clients = _rank_entries(entries, entry_type="income", only_pending=True)
    pending_suppliers = _rank_entries(entries, entry_type="expense", only_pending=True)

    pending_income_total = sum(value for _, value in pending_clients)
    top3_pending = sum(value for _, value in pending_clients[:3])
    concentration = 0.0 if pending_income_total <= 0 else (top3_pending / pending_income_total) * 100

    due_30_income, due_30_expense, due_30_count = _due_30_amounts(summary)

    attention: list[str] = []
    if summary.projected_balance < 0:
        attention.append(
            f"Saldo projetado negativo em {_money(abs(summary.projected_balance))}."
        )
    if summary.period_expense > summary.period_income:
        attention.append(
            f"Saídas superam receitas em {_money(summary.period_expense - summary.period_income)} no período."
        )
    if summary.overdue_income > 0:
        attention.append(
            f"Há {_money(summary.overdue_income)} em contas a receber vencidas."
        )
    if summary.overdue_expense > 0:
        attention.append(
            f"Há {_money(summary.overdue_expense)} em contas a pagar vencidas."
        )
    if concentration >= 50 and pending_income_total > 0:
        attention.append(
            f"{concentration:.1f}% do valor pendente a receber está concentrado nos 3 maiores clientes."
        )
    if due_30_expense > due_30_income and due_30_expense > 0:
        attention.append(
            f"Nos próximos 30 dias, pagamentos previstos excedem recebimentos em {_money(due_30_expense - due_30_income)}."
        )
    if not attention:
        attention.append("Nenhum ponto crítico identificado pelas regras automáticas deste relatório.")

    month_variations: list[tuple[str, float | None]] = []
    previous_income: float | None = None
    for point in summary.monthly_flow:
        variation = None if previous_income is None else _percent_change(point.income, previous_income)
        month_variations.append((point.label, variation))
        previous_income = point.income

    return {
        "top_income": top_income,
        "top_expense": top_expense,
        "pending_clients": pending_clients,
        "pending_suppliers": pending_suppliers,
        "concentration": concentration,
        "due_30_income": due_30_income,
        "due_30_expense": due_30_expense,
        "due_30_count": due_30_count,
        "attention": attention,
        "month_variations": month_variations,
    }


def _variation_label(value: float | None) -> str:
    if value is None:
        return "-"
    prefix = "+" if value > 0 else ""
    return f"{prefix}{value:.1f}%"


def generate_finance_pdf(
    summary: FinanceSummary,
    entries: Sequence[object],
    *,
    company_label: str,
) -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        rightMargin=12 * mm,
        leftMargin=12 * mm,
        topMargin=12 * mm,
        bottomMargin=12 * mm,
        title=f"Relatório Financeiro - {company_label}",
        author="NEXUS Enterprise",
    )

    styles = getSampleStyleSheet()
    title = ParagraphStyle(
        "FinanceTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=18,
        leading=22,
        textColor=colors.HexColor("#0F2740"),
        alignment=TA_LEFT,
        spaceAfter=3 * mm,
    )
    section = ParagraphStyle(
        "FinanceSection",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=11,
        textColor=colors.HexColor("#123B5D"),
        spaceBefore=4 * mm,
        spaceAfter=2 * mm,
    )
    small = ParagraphStyle(
        "FinanceSmall",
        parent=styles["BodyText"],
        fontSize=8,
        leading=10,
        textColor=colors.HexColor("#41576B"),
    )
    centered = ParagraphStyle("FinanceCentered", parent=small, alignment=TA_CENTER)

    insights = _executive_insights(summary, entries)

    story: list[object] = []
    story.append(Paragraph("NEXUS ENTERPRISE - RELATÓRIO FINANCEIRO", title))
    story.append(Paragraph(
        f"<b>{escape(company_label)}</b> &nbsp;&nbsp;|&nbsp;&nbsp; Período: {_period_label(summary)} &nbsp;&nbsp;|&nbsp;&nbsp; Base: {escape(_basis_label(summary))}",
        small,
    ))
    story.append(Spacer(1, 4 * mm))

    kpi_rows = [
        ["Saldo atual", "Receitas", "Saídas", "Resultado", "Saldo projetado", "Atrasado a receber", "Atrasado a pagar"],
        [
            _money(summary.current_balance),
            _money(summary.period_income),
            _money(summary.period_expense),
            _money(summary.period_result),
            _money(summary.projected_balance),
            _money(summary.overdue_income),
            _money(summary.overdue_expense),
        ],
    ]
    kpis = Table(kpi_rows, repeatRows=1, colWidths=[36 * mm] * 7)
    kpis.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#123B5D")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, 1), (-1, 1), "Helvetica-Bold"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("FONTSIZE", (0, 0), (-1, -1), 7.5),
        ("BACKGROUND", (0, 1), (-1, 1), colors.HexColor("#F4F7FA")),
        ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#B8C7D3")),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    story.append(kpis)

    story.append(Paragraph("Resumo para fechamento", section))
    close_rows = [
        ["Lançamentos", "Recebido", "Pago", "A receber", "A pagar", "Vencidos", "Próx. 7 dias"],
        [
            str(summary.period_entry_count),
            _money(summary.settled_income),
            _money(summary.settled_expense),
            _money(summary.pending_income),
            _money(summary.pending_expense),
            str(summary.overdue_count),
            str(summary.due_soon_count),
        ],
    ]
    close_table = Table(close_rows, colWidths=[36 * mm] * 7)
    close_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#DCEAF4")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.3, colors.HexColor("#B8C7D3")),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(close_table)

    story.append(Paragraph("Análise executiva", section))
    due30_rows = [
        ["Indicador", "Valor"],
        ["Recebimentos previstos em até 30 dias", _money(insights["due_30_income"])],
        ["Pagamentos previstos em até 30 dias", _money(insights["due_30_expense"])],
        ["Títulos com vencimento em até 30 dias", str(insights["due_30_count"])],
        ["Concentração dos 3 maiores clientes a receber", f'{insights["concentration"]:.1f}%'],
    ]
    due30_table = Table(due30_rows, colWidths=[92 * mm, 60 * mm])
    due30_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#DCEAF4")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ALIGN", (1, 1), (1, -1), "RIGHT"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#C6D1DA")),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    story.append(due30_table)

    story.append(Paragraph("Pontos de atenção", section))
    for item in insights["attention"]:
        story.append(Paragraph(f"• {escape(str(item))}", small))

    story.append(Paragraph("Desempenho mês a mês", section))
    monthly_rows = [["Mês", "Receitas", "Var. mês", "Saídas", "Resultado", "Recebido", "Pago", "A receber", "A pagar"]]
    monthly_rows.extend([
        [
            point.label,
            _money(point.income),
            _variation_label(insights["month_variations"][index][1]),
            _money(point.expense),
            _money(point.result),
            _money(point.settled_income),
            _money(point.settled_expense),
            _money(point.pending_income),
            _money(point.pending_expense),
        ]
        for index, point in enumerate(summary.monthly_flow)
    ])
    monthly = Table(monthly_rows, repeatRows=1, colWidths=[22 * mm, 29 * mm, 20 * mm] + [29 * mm] * 6)
    monthly.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#123B5D")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
        ("FONTSIZE", (0, 0), (-1, -1), 7.2),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F7F9FB")]),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#C6D1DA")),
        ("TOPPADDING", (0, 0), (-1, -1), 3.5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3.5),
    ]))
    story.append(monthly)

    story.append(Paragraph("Maiores movimentações e concentrações", section))
    ranking_rows = [["Top receitas", "Valor", "Top despesas", "Valor"]]
    max_rank = max(len(insights["top_income"]), len(insights["top_expense"]), 1)
    for index in range(max_rank):
        income_name, income_value = insights["top_income"][index] if index < len(insights["top_income"]) else ("-", 0)
        expense_name, expense_value = insights["top_expense"][index] if index < len(insights["top_expense"]) else ("-", 0)
        ranking_rows.append([
            Paragraph(escape(str(income_name)), small),
            _money(income_value),
            Paragraph(escape(str(expense_name)), small),
            _money(expense_value),
        ])
    ranking = Table(ranking_rows, repeatRows=1, colWidths=[70 * mm, 34 * mm, 70 * mm, 34 * mm])
    ranking.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#123B5D")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ALIGN", (1, 1), (1, -1), "RIGHT"),
        ("ALIGN", (3, 1), (3, -1), "RIGHT"),
        ("FONTSIZE", (0, 0), (-1, -1), 7.5),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#C6D1DA")),
    ]))
    story.append(ranking)

    story.append(Spacer(1, 2 * mm))
    exposure_rows = [["Maiores clientes a receber", "Valor", "Maiores fornecedores a pagar", "Valor"]]
    max_exposure = max(len(insights["pending_clients"]), len(insights["pending_suppliers"]), 1)
    for index in range(max_exposure):
        client_name, client_value = insights["pending_clients"][index] if index < len(insights["pending_clients"]) else ("-", 0)
        supplier_name, supplier_value = insights["pending_suppliers"][index] if index < len(insights["pending_suppliers"]) else ("-", 0)
        exposure_rows.append([
            Paragraph(escape(str(client_name)), small),
            _money(client_value),
            Paragraph(escape(str(supplier_name)), small),
            _money(supplier_value),
        ])
    exposure = Table(exposure_rows, repeatRows=1, colWidths=[70 * mm, 34 * mm, 70 * mm, 34 * mm])
    exposure.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#DCEAF4")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ALIGN", (1, 1), (1, -1), "RIGHT"),
        ("ALIGN", (3, 1), (3, -1), "RIGHT"),
        ("FONTSIZE", (0, 0), (-1, -1), 7.5),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#C6D1DA")),
    ]))
    story.append(exposure)

    story.append(PageBreak())
    story.append(Paragraph("Previsão de fluxo - 13 semanas", section))
    weekly_rows = [["Sem.", "Início", "Fim", "Saldo inicial", "Entradas", "Saídas", "Venc. rec.", "Venc. pag.", "Resultado", "Saldo final", "Títulos"]]
    weekly_rows.extend([
        [
            f"S{item.week_number}",
            item.start_date.strftime("%d/%m/%Y"),
            item.end_date.strftime("%d/%m/%Y"),
            _money(item.opening_balance),
            _money(item.income),
            _money(item.expense),
            _money(item.overdue_income),
            _money(item.overdue_expense),
            _money(item.net),
            _money(item.closing_balance),
            str(item.entry_count),
        ]
        for item in summary.weekly_forecast_13w
    ])
    weekly = Table(weekly_rows, repeatRows=1, colWidths=[12 * mm, 22 * mm, 22 * mm] + [25 * mm] * 7 + [14 * mm])
    weekly.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#123B5D")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ALIGN", (3, 1), (-2, -1), "RIGHT"),
        ("ALIGN", (0, 0), (2, -1), "CENTER"),
        ("FONTSIZE", (0, 0), (-1, -1), 6.7),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F7F9FB")]),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#C6D1DA")),
    ]))
    story.append(weekly)

    story.append(Paragraph("Aging de títulos pendentes", section))
    aging_rows = [["Faixa", "Quantidade", "A receber", "A pagar"]]
    aging_rows.extend([[item.label, str(item.count), _money(item.income), _money(item.expense)] for item in summary.aging])
    aging = Table(aging_rows, repeatRows=1, colWidths=[70 * mm, 35 * mm, 55 * mm, 55 * mm])
    aging.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#DCEAF4")),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("ALIGN", (1, 1), (-1, -1), "RIGHT"),
        ("FONTSIZE", (0, 0), (-1, -1), 7.5),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#C6D1DA")),
    ]))
    story.append(aging)

    story.append(PageBreak())
    story.append(Paragraph("Lançamentos do período", section))
    entry_rows: list[list[object]] = [["Tipo", "Cliente / fornecedor", "Descrição", "Documento", "Emissão", "Vencimento", "Baixa", "Banco", "Status", "Valor"]]
    for entry in entries:
        entry_type = str(_entry_value(entry, "entry_type", ""))
        document = _entry_value(entry, "nfse_number") or _entry_value(entry, "nfe_number") or _entry_value(entry, "document_number") or "-"
        issue_date = _entry_value(entry, "issue_date")
        due_date = _entry_value(entry, "due_date")
        settlement_date = _entry_value(entry, "settlement_date")
        entry_rows.append([
            ENTRY_TYPE_LABELS.get(entry_type, entry_type),
            Paragraph(escape(str(_entry_value(entry, "counterparty_name", ""))), small),
            Paragraph(escape(str(_entry_value(entry, "description", ""))), small),
            str(document),
            issue_date.strftime("%d/%m/%Y") if issue_date else "-",
            due_date.strftime("%d/%m/%Y") if due_date else "-",
            settlement_date.strftime("%d/%m/%Y") if settlement_date else "-",
            str(_entry_value(entry, "bank_name", "-")),
            STATUS_LABELS.get(str(_entry_value(entry, "status", "")), str(_entry_value(entry, "status", ""))),
            _money(_entry_value(entry, "amount", 0)),
        ])
    if len(entry_rows) == 1:
        entry_rows.append(["-", "Nenhum lançamento no período", "-", "-", "-", "-", "-", "-", "-", _money(0)])
    entry_table = Table(
        entry_rows,
        repeatRows=1,
        colWidths=[18 * mm, 43 * mm, 54 * mm, 25 * mm, 21 * mm, 21 * mm, 21 * mm, 27 * mm, 22 * mm, 28 * mm],
    )
    entry_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#123B5D")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (-1, 1), (-1, -1), "RIGHT"),
        ("FONTSIZE", (0, 0), (-1, -1), 6.6),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F7F9FB")]),
        ("GRID", (0, 0), (-1, -1), 0.2, colors.HexColor("#C6D1DA")),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(entry_table)
    story.append(Spacer(1, 3 * mm))
    story.append(Paragraph("Relatório gerado pelo NEXUS Enterprise. Valores refletem os filtros e a base de data informados no cabeçalho.", centered))

    doc.build(story)
    return buffer.getvalue()


def _column_name(index: int) -> str:
    name = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        name = chr(65 + remainder) + name
    return name


def _xlsx_cell(row: int, col: int, value: object, style: int = 0) -> str:
    ref = f"{_column_name(col)}{row}"
    style_attr = f' s="{style}"' if style else ""
    if value is None:
        return f'<c r="{ref}"{style_attr}/>'
    if isinstance(value, bool):
        return f'<c r="{ref}" t="b"{style_attr}><v>{1 if value else 0}</v></c>'
    if isinstance(value, (int, float, Decimal)):
        return f'<c r="{ref}"{style_attr}><v>{value}</v></c>'
    text = escape(str(value))
    preserve = ' xml:space="preserve"' if text.startswith(" ") or text.endswith(" ") else ""
    return f'<c r="{ref}" t="inlineStr"{style_attr}><is><t{preserve}>{text}</t></is></c>'


def _sheet_xml(rows: Sequence[Sequence[tuple[object, int] | object]], widths: Sequence[float] | None = None) -> str:
    cols = ""
    if widths:
        cols = "<cols>" + "".join(
            f'<col min="{i}" max="{i}" width="{width}" customWidth="1"/>'
            for i, width in enumerate(widths, start=1)
        ) + "</cols>"
    row_xml: list[str] = []
    for row_index, row in enumerate(rows, start=1):
        cells: list[str] = []
        for col_index, raw in enumerate(row, start=1):
            if isinstance(raw, tuple) and len(raw) == 2:
                value, style = raw
            else:
                value, style = raw, 0
            cells.append(_xlsx_cell(row_index, col_index, value, int(style)))
        row_xml.append(f'<row r="{row_index}">{"".join(cells)}</row>')
    return (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f'{cols}<sheetData>{"".join(row_xml)}</sheetData></worksheet>'
    )


def generate_finance_xlsx(
    summary: FinanceSummary,
    entries: Sequence[object],
    *,
    company_label: str,
) -> bytes:
    insights = _executive_insights(summary, entries)
    sheets: list[tuple[str, list[list[tuple[object, int] | object]], list[float]]] = []

    executive_rows: list[list[tuple[object, int] | object]] = [
        [("NEXUS ENTERPRISE - ANÁLISE EXECUTIVA", 1)],
        [("Empresa", 2), company_label],
        [("Período", 2), _period_label(summary)],
        [("Base da data", 2), _basis_label(summary)],
        [],
        [("Indicador", 2), ("Valor", 2)],
        ["Saldo projetado", (summary.projected_balance, 3)],
        ["Vencido a receber", (summary.overdue_income, 3)],
        ["Vencido a pagar", (summary.overdue_expense, 3)],
        ["Receber em até 30 dias", (insights["due_30_income"], 3)],
        ["Pagar em até 30 dias", (insights["due_30_expense"], 3)],
        ["Títulos em até 30 dias", (insights["due_30_count"], 4)],
        ["Concentração Top 3 clientes", f'{insights["concentration"]:.1f}%'],
        [],
        [("Pontos de atenção", 2)],
    ]
    executive_rows.extend([[str(item)] for item in insights["attention"]])
    executive_rows.extend([[], [("Top 5 receitas", 2), ("Valor", 2), ("Top 5 despesas", 2), ("Valor", 2)]])
    max_rank = max(len(insights["top_income"]), len(insights["top_expense"]), 1)
    for index in range(max_rank):
        income_name, income_value = insights["top_income"][index] if index < len(insights["top_income"]) else ("-", 0)
        expense_name, expense_value = insights["top_expense"][index] if index < len(insights["top_expense"]) else ("-", 0)
        executive_rows.append([income_name, (income_value, 3), expense_name, (expense_value, 3)])
    executive_rows.extend([[], [("Clientes com maior valor a receber", 2), ("Valor", 2), ("Fornecedores com maior valor a pagar", 2), ("Valor", 2)]])
    max_exposure = max(len(insights["pending_clients"]), len(insights["pending_suppliers"]), 1)
    for index in range(max_exposure):
        client_name, client_value = insights["pending_clients"][index] if index < len(insights["pending_clients"]) else ("-", 0)
        supplier_name, supplier_value = insights["pending_suppliers"][index] if index < len(insights["pending_suppliers"]) else ("-", 0)
        executive_rows.append([client_name, (client_value, 3), supplier_name, (supplier_value, 3)])
    sheets.append(("Executivo", executive_rows, [38, 20, 38, 20]))

    summary_rows: list[list[tuple[object, int] | object]] = [
        [("NEXUS ENTERPRISE - RELATÓRIO FINANCEIRO", 1)],
        [("Empresa", 2), company_label],
        [("Período", 2), _period_label(summary)],
        [("Base da data", 2), _basis_label(summary)],
        [],
        [("Indicador", 2), ("Valor", 2)],
        ["Saldo atual", (summary.current_balance, 3)],
        ["Receitas lançadas", (summary.period_income, 3)],
        ["Saídas lançadas", (summary.period_expense, 3)],
        ["Resultado", (summary.period_result, 3)],
        ["Recebido", (summary.settled_income, 3)],
        ["Pago", (summary.settled_expense, 3)],
        ["A receber", (summary.pending_income, 3)],
        ["A pagar", (summary.pending_expense, 3)],
        ["Saldo projetado", (summary.projected_balance, 3)],
        ["Atrasado a receber", (summary.overdue_income, 3)],
        ["Atrasado a pagar", (summary.overdue_expense, 3)],
        ["Lançamentos do período", (summary.period_entry_count, 4)],
        ["Títulos vencidos", (summary.overdue_count, 4)],
        ["Próximos 7 dias", (summary.due_soon_count, 4)],
    ]
    sheets.append(("Resumo", summary_rows, [30, 24]))

    entry_rows: list[list[tuple[object, int] | object]] = [[
        ("Tipo", 2), ("Empresa", 2), ("Cliente / fornecedor", 2), ("Descrição", 2), ("Documento", 2),
        ("Emissão", 2), ("Competência", 2), ("Vencimento", 2), ("Baixa", 2), ("Banco", 2), ("Status", 2), ("Valor", 2),
    ]]
    for entry in entries:
        entry_type = str(_entry_value(entry, "entry_type", ""))
        company = str(_entry_value(entry, "company_code", ""))
        document = _entry_value(entry, "nfse_number") or _entry_value(entry, "nfe_number") or _entry_value(entry, "document_number") or ""
        entry_rows.append([
            ENTRY_TYPE_LABELS.get(entry_type, entry_type),
            COMPANY_LABELS.get(company, company),
            str(_entry_value(entry, "counterparty_name", "")),
            str(_entry_value(entry, "description", "")),
            str(document),
            _entry_value(entry, "issue_date", ""),
            _entry_value(entry, "posting_date", ""),
            _entry_value(entry, "due_date", ""),
            _entry_value(entry, "settlement_date", ""),
            str(_entry_value(entry, "bank_name", "")),
            STATUS_LABELS.get(str(_entry_value(entry, "status", "")), str(_entry_value(entry, "status", ""))),
            (_entry_value(entry, "amount", 0), 3),
        ])
    sheets.append(("Lançamentos", entry_rows, [13, 23, 28, 38, 18, 14, 14, 14, 14, 18, 14, 16]))

    monthly_rows: list[list[tuple[object, int] | object]] = [[
        ("Mês", 2), ("Receitas", 2), ("Var. receitas", 2), ("Saídas", 2), ("Resultado", 2), ("Recebido", 2), ("Pago", 2), ("A receber", 2), ("A pagar", 2),
    ]]
    for index, item in enumerate(summary.monthly_flow):
        variation = insights["month_variations"][index][1]
        monthly_rows.append([
            item.label, (item.income, 3), _variation_label(variation), (item.expense, 3), (item.result, 3),
            (item.settled_income, 3), (item.settled_expense, 3), (item.pending_income, 3), (item.pending_expense, 3),
        ])
    sheets.append(("Mensal", monthly_rows, [16, 18, 16] + [18] * 6))

    aging_rows: list[list[tuple[object, int] | object]] = [[("Faixa", 2), ("Quantidade", 2), ("A receber", 2), ("A pagar", 2)]]
    for item in summary.aging:
        aging_rows.append([item.label, (item.count, 4), (item.income, 3), (item.expense, 3)])
    sheets.append(("Aging", aging_rows, [28, 14, 18, 18]))

    weekly_rows: list[list[tuple[object, int] | object]] = [[
        ("Semana", 2), ("Início", 2), ("Fim", 2), ("Saldo inicial", 2), ("Entradas", 2), ("Saídas", 2),
        ("Vencido a receber", 2), ("Vencido a pagar", 2), ("Resultado", 2), ("Saldo final", 2), ("Títulos", 2),
    ]]
    for item in summary.weekly_forecast_13w:
        weekly_rows.append([
            f"S{item.week_number}", item.start_date, item.end_date, (item.opening_balance, 3), (item.income, 3),
            (item.expense, 3), (item.overdue_income, 3), (item.overdue_expense, 3), (item.net, 3), (item.closing_balance, 3), (item.entry_count, 4),
        ])
    sheets.append(("Fluxo 13 semanas", weekly_rows, [12, 14, 14] + [18] * 7 + [12]))

    out = BytesIO()
    with ZipFile(out, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr(
            "[Content_Types].xml",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
            '<Default Extension="xml" ContentType="application/xml"/>'
            '<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
            '<Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
            + "".join(
                f'<Override PartName="/xl/worksheets/sheet{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
                for i in range(1, len(sheets) + 1)
            )
            + '</Types>',
        )
        archive.writestr(
            "_rels/.rels",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>'
            '</Relationships>',
        )
        workbook_sheets = "".join(
            f'<sheet name="{escape(name)}" sheetId="{i}" r:id="rId{i}"/>'
            for i, (name, _, _) in enumerate(sheets, start=1)
        )
        archive.writestr(
            "xl/workbook.xml",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            f'<sheets>{workbook_sheets}</sheets></workbook>',
        )
        relationships = "".join(
            f'<Relationship Id="rId{i}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{i}.xml"/>'
            for i in range(1, len(sheets) + 1)
        )
        relationships += f'<Relationship Id="rId{len(sheets) + 1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
        archive.writestr(
            "xl/_rels/workbook.xml.rels",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            f'{relationships}</Relationships>',
        )
        archive.writestr(
            "xl/styles.xml",
            '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
            '<numFmts count="1"><numFmt numFmtId="164" formatCode="[$R$-pt-BR] #,##0.00;[Red]-[$R$-pt-BR] #,##0.00"/></numFmts>'
            '<fonts count="3"><font><sz val="11"/><name val="Calibri"/></font><font><b/><sz val="16"/><color rgb="FF123B5D"/><name val="Calibri"/></font><font><b/><color rgb="FFFFFFFF"/><name val="Calibri"/></font></fonts>'
            '<fills count="3"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill><fill><patternFill patternType="solid"><fgColor rgb="FF123B5D"/><bgColor indexed="64"/></patternFill></fill></fills>'
            '<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>'
            '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
            '<cellXfs count="5">'
            '<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>'
            '<xf numFmtId="0" fontId="1" fillId="0" borderId="0" xfId="0" applyFont="1"/>'
            '<xf numFmtId="0" fontId="2" fillId="2" borderId="0" xfId="0" applyFont="1" applyFill="1"/>'
            '<xf numFmtId="164" fontId="0" fillId="0" borderId="0" xfId="0" applyNumberFormat="1"/>'
            '<xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>'
            '</cellXfs></styleSheet>',
        )
        for index, (_, rows, widths) in enumerate(sheets, start=1):
            archive.writestr(f"xl/worksheets/sheet{index}.xml", _sheet_xml(rows, widths))

    return out.getvalue()
