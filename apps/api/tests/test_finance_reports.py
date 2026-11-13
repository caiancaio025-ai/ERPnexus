from datetime import date
from types import SimpleNamespace
from zipfile import ZipFile
from io import BytesIO

from app.finance.reporting import (
    company_report_label,
    finance_report_filename,
    generate_finance_pdf,
    generate_finance_xlsx,
)
from app.finance.schemas import AgingBucket, FinanceSummary, MonthlyFlowPoint, WeeklyForecastPoint


def _summary() -> FinanceSummary:
    return FinanceSummary(
        current_balance=12500,
        period_income=15000,
        period_expense=7000,
        period_result=8000,
        settled_income=9000,
        settled_expense=4000,
        pending_income=6000,
        pending_expense=3000,
        overdue_income=1000,
        overdue_expense=500,
        period_entry_count=4,
        period_income_count=2,
        period_expense_count=2,
        period_start=date(2026, 10, 1),
        period_end=date(2026, 10, 31),
        date_basis="posting",
        projected_balance=15500,
        overdue_count=1,
        due_soon_count=2,
        kpis=[],
        urgent_events=[],
        income_events=[],
        expense_events=[],
        cash_flow=[],
        forecast_flow=[],
        weekly_forecast_13w=[
            WeeklyForecastPoint(
                week_number=1,
                start_date=date(2026, 10, 8),
                end_date=date(2026, 10, 14),
                opening_balance=12500,
                income=5000,
                expense=2500,
                overdue_income=1000,
                overdue_expense=500,
                net=3000,
                closing_balance=15500,
                entry_count=4,
            )
        ],
        aging=[
            AgingBucket(key="overdue_1_30", label="Vencido 1-30 dias", income=1000, expense=500, count=2)
        ],
        monthly_flow=[
            MonthlyFlowPoint(
                month=10,
                label="Outubro",
                income=15000,
                expense=7000,
                settled_income=9000,
                settled_expense=4000,
                pending_income=6000,
                pending_expense=3000,
                result=8000,
            )
        ],
    )


def _entries():
    return [
        SimpleNamespace(
            entry_type="income",
            company_code="universo_eletronica",
            counterparty_name="Cliente Teste",
            description="Manutenção OS-123",
            nfse_number="1001",
            nfe_number=None,
            document_number=None,
            issue_date=date(2026, 10, 2),
            posting_date=date(2026, 10, 2),
            due_date=date(2026, 10, 20),
            settlement_date=None,
            bank_name="Bradesco",
            status="pending",
            amount=15000,
        ),
        SimpleNamespace(
            entry_type="expense",
            company_code="universo_eletronica",
            counterparty_name="Fornecedor Teste",
            description="Peças",
            nfse_number=None,
            nfe_number=None,
            document_number="DOC-9",
            issue_date=date(2026, 10, 3),
            posting_date=date(2026, 10, 3),
            due_date=date(2026, 10, 18),
            settlement_date=date(2026, 10, 4),
            bank_name="Itaú",
            status="paid",
            amount=7000,
        ),
    ]


def test_finance_pdf_report_is_valid_pdf() -> None:
    content = generate_finance_pdf(_summary(), _entries(), company_label="Universo Eletrônica")
    assert content.startswith(b"%PDF-")
    assert len(content) > 3000


def test_finance_xlsx_report_has_expected_sheets_and_content() -> None:
    content = generate_finance_xlsx(_summary(), _entries(), company_label="Universo Eletrônica")
    assert content.startswith(b"PK")
    with ZipFile(BytesIO(content)) as workbook:
        names = set(workbook.namelist())
        assert "xl/workbook.xml" in names
        assert "xl/worksheets/sheet1.xml" in names
        workbook_xml = workbook.read("xl/workbook.xml").decode("utf-8")
        assert "Executivo" in workbook_xml
        assert "Resumo" in workbook_xml
        assert "Lançamentos" in workbook_xml
        assert "Mensal" in workbook_xml
        assert "Aging" in workbook_xml
        assert "Fluxo 13 semanas" in workbook_xml
        executive_xml = workbook.read("xl/worksheets/sheet1.xml").decode("utf-8")
        assert "ANÁLISE EXECUTIVA" in executive_xml
        assert "Pontos de atenção" in executive_xml
        assert "Top 5 receitas" in executive_xml

        entries_xml = workbook.read("xl/worksheets/sheet3.xml").decode("utf-8")
        assert "Cliente Teste" in entries_xml
        assert "Fornecedor Teste" in entries_xml


def test_finance_report_labels_and_filename() -> None:
    assert company_report_label("universo_eletronica", False) == "Universo Eletrônica"
    assert company_report_label(None, True) == "Grupo consolidado"
    assert finance_report_filename("pdf", "universo_eletronica", False, date(2026, 10, 31)) == (
        "financeiro_universo_eletronica_2026-10-31.pdf"
    )


def test_executive_report_contains_rankings_and_attention() -> None:
    content = generate_finance_pdf(_summary(), _entries(), company_label="Universo Eletrônica")
    assert content.startswith(b"%PDF-")
    assert len(content) > 4000
