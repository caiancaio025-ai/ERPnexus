"""Regressão do painel por função: consultas e dados financeiros só na Gestão.

Os testes usam instruções SQL reais do SQLAlchemy e uma sessão simulada:
não dependem de Postgres para verificar a política de visibilidade.
"""
import asyncio
from types import SimpleNamespace

from app.dashboard.service import build_summary, dashboard_audience


class _Rows:
    def all(self):
        return []


class QuerySpy:
    def __init__(self):
        self.statements = []

    async def scalar(self, query):
        self.statements.append(str(query))
        return 0

    async def scalars(self, query):
        self.statements.append(str(query))
        return _Rows()


def _summary(role, modules=None):
    user = SimpleNamespace(id=20, role=role, name="Teste", modules=modules or [])
    db = QuerySpy()
    result = asyncio.run(build_summary(user, db))
    return result, db


def test_audience_does_not_inherit_adm_or_lab_modules():
    """Um perfil não é transformado em Gestão por ter módulos legados."""
    all_modules = ["dashboard", "financeiro", "laboratorio", "compras", "estoque"]
    assert dashboard_audience(SimpleNamespace(role="admin", modules=all_modules)) == "admin"
    assert dashboard_audience(SimpleNamespace(role="lab", modules=all_modules)) == "lab"
    assert dashboard_audience(SimpleNamespace(role="tecnico", modules=all_modules)) == "lab"
    assert dashboard_audience(SimpleNamespace(role="gestao", modules=all_modules)) == "gestao"


def test_gestao_sees_all_departments():
    summary, spy = _summary("gestao")
    assert summary.schema_version == "3"
    assert {queue.section for queue in summary.work_queues} == {
        "laboratorio", "orcamentos", "compras", "financeiro",
    }
    assert {queue.key for queue in summary.work_queues} >= {
        "lab_entries", "lab_approved", "quotes_pending", "requests_buy",
        "requests_arrival", "finance_overdue", "finance_pending", "recent_invoices",
    }
    assert any("financial_entries" in sql for sql in spy.statements)


def test_admin_only_quotes_even_if_modules_allow_all():
    summary, spy = _summary("admin", ["laboratorio", "financeiro", "compras", "estoque"])
    assert {queue.key for queue in summary.work_queues} == {"quotes_pending"}
    assert set(alert.key for alert in summary.alerts) == {"unread_notifications", "quotes_pending"}
    assert not summary.purchase_events
    assert all("financial_entries" not in sql and "purchase_orders" not in sql
               for sql in spy.statements)


def test_lab_never_receives_finance_or_purchase_management():
    for role in ("lab", "tecnico", "laboratorio"):
        summary, spy = _summary(role, ["dashboard", "financeiro", "compras", "laboratorio"])
        assert {q.key for q in summary.work_queues} == {"lab_entries", "lab_approved"}
        assert not any(q.section == "financeiro" for q in summary.work_queues)
        assert all("financial_entries" not in sql for sql in spy.statements)


def test_compras_sees_requests_not_sensitive_finance():
    summary, spy = _summary("compras", ["dashboard", "compras", "financeiro"])
    assert {queue.key for queue in summary.work_queues} == {
        "requests_approval", "requests_buy", "requests_arrival",
    }
    assert not any("financial_entries" in sql for sql in spy.statements)
    assert all(action.key != "new_budget" for action in summary.quick_actions)


def test_stock_only_receipt_tasks():
    summary, spy = _summary("estoque", ["dashboard", "estoque"])
    assert {queue.key for queue in summary.work_queues} == {"stock_to_receive", "stock_to_deliver"}
    assert all(queue.target == "/estoque" for queue in summary.work_queues)
    assert not any("financial_entries" in sql for sql in spy.statements)


def test_consultation_user_has_no_workflows():
    summary, spy = _summary("consulta", ["dashboard"])
    assert not summary.work_queues
    assert not summary.quick_actions
    assert not any("financial_entries" in sql or "laboratory_work_orders" in sql
                   for sql in spy.statements)


def test_work_order_item_opens_precise_os_tab_without_duplicating_prefix():
    from datetime import date
    from app.dashboard.service import _os_item
    order = SimpleNamespace(
        id=81, number="OS-39405", customer_name="CAPRICHE", opened_at=date(2026, 11, 17),
        equipment=SimpleNamespace(manufacturer="WEG", model="CFW11", equipment_type="Inversor"),
    )
    item = _os_item(order, "Analisado", "quote")
    assert item.title == "OS 39405"
    assert item.description == "WEG CFW11"
    assert item.meta == "CAPRICHE"
    assert item.target == "/laboratorio?os=81&aba=quote"


def test_finance_entry_link_opens_specific_entry():
    from datetime import date
    from decimal import Decimal
    from app.dashboard.service import _finance_queue

    class FinanceSpy(QuerySpy):
        async def scalars(self, query):
            self.statements.append(str(query))
            return SimpleNamespace(all=lambda: [SimpleNamespace(
                id=47, counterparty_name="Cliente Exemplo", description="NF 123",
                entry_type="income", amount=Decimal("2500.00"), due_date=date(2026, 11, 19),
            )])

    result = asyncio.run(_finance_queue(FinanceSpy(), key="finance_pending", title="Pendentes",
                                          description="A vencer", tone="warning",
                                          today=date(2026, 11, 17), overdue=False))
    assert result.items[0].target == "/financeiro?lancamento=47"
    assert result.items[0].status == "A receber"
    assert "2.500,00" in result.items[0].meta


def test_purchase_request_link_opens_exact_request():
    from datetime import datetime
    from app.dashboard.service import _materials_queue

    class MaterialSpy(QuerySpy):
        async def scalars(self, query):
            self.statements.append(str(query))
            return SimpleNamespace(all=lambda: [SimpleNamespace(
                id=73, code="SC-2026-0059", item_name="IGBT", work_order_id=None,
                quantity=2, status="approved", created_at=datetime(2026, 11, 17),
            )])

    result = asyncio.run(_materials_queue(MaterialSpy(), key="requests_buy", title="Comprar",
                                            description="Pendências", statuses=("approved",), tone="info"))
    assert result.items[0].target == "/compras?view=requests&solicitacao=73"
    assert "IGBT" in result.items[0].title
