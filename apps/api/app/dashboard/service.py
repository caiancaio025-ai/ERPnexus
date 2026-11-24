"""Painel inicial por responsabilidade, sem vazar dados entre perfis.

Os números são calculados no banco; a amostra visual é limitada a cinco itens
por fila. A escolha das filas e dos links acontece no servidor. Consultas de
valores financeiros são exclusivas da Gestão, inclusive quando um usuário LAB
ou ADM possui módulos legados em seu cadastro.
"""
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import exists, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload, load_only, raiseload

from app.auth.access import (
    MODULE_INVENTORY, MODULE_LABORATORY, MODULE_PURCHASING,
    user_can_create_quote, user_has_module,
)
from app.auth.models import User
from app.dashboard.schemas import (
    Alert, DashboardSummary, MonthlyEquipmentEntries, PurchaseEvent,
    QuickAction, WorkItem, WorkQueue,
)
from app.finance.models import FinancialEntry
from app.laboratory.models import LaboratoryQuote, LaboratoryWorkOrder
from app.laboratory.service import TERMINAL_STATUSES
from app.notifications.models import Notification
from app.purchasing.material_models import MaterialRequest
from app.purchasing.models import PurchaseOrder

_MONTHS = ("janeiro", "fevereiro", "março", "abril", "maio", "junho",
           "julho", "agosto", "setembro", "outubro", "novembro", "dezembro")
_OPEN_PURCHASE_STATUSES = ("awaiting_payment", "ordered", "processing", "shipped", "customs")


@dataclass(frozen=True)
class DashboardPeriod:
    """Filtro de consulta, separado da regra de autorização de cada perfil."""
    start: date | None = None
    end: date | None = None
    label: str = "Todo o histórico"

    @property
    def active(self) -> bool:
        return self.start is not None or self.end is not None


def resolve_dashboard_period(
    preset: str = "todos", start: date | None = None, end: date | None = None,
    *, today: date | None = None,
) -> DashboardPeriod:
    """Resolve datas na região do servidor, sem reescrever dados legados."""
    if today is None:
        today = datetime.now(ZoneInfo("America/Recife")).date()
    if preset == "todos":
        return DashboardPeriod()
    if preset == "mes":
        first_next_month = (today.replace(day=28) + timedelta(days=4)).replace(day=1)
        return DashboardPeriod(today.replace(day=1), first_next_month - timedelta(days=1), "Este mês")
    if preset == "30d":
        return DashboardPeriod(today - timedelta(days=29), today, "Últimos 30 dias")
    if preset == "90d":
        return DashboardPeriod(today - timedelta(days=89), today, "Últimos 90 dias")
    if preset == "ano":
        return DashboardPeriod(today.replace(month=1, day=1), today.replace(month=12, day=31), "Este ano")
    if preset == "personalizado":
        if start is None and end is None:
            raise ValueError("Informe pelo menos uma data para o período personalizado.")
        if start is not None and end is not None and start > end:
            raise ValueError("A data inicial não pode ser posterior à data final.")
        if start and end:
            label = f"De {start:%d/%m/%Y} até {end:%d/%m/%Y}"
        elif start:
            label = f"A partir de {start:%d/%m/%Y}"
        else:
            label = f"Até {end:%d/%m/%Y}"
        return DashboardPeriod(start, end, label)
    raise ValueError("Período inválido.")


def period_criteria(column, period: DashboardPeriod, *, timestamp: bool = False) -> list:
    """Para timestamps, o final é exclusivo à meia-noite do dia seguinte."""
    criteria = []
    tz = ZoneInfo("America/Recife")
    if period.start is not None:
        beginning = datetime.combine(period.start, time.min, tzinfo=tz) if timestamp else period.start
        criteria.append(column >= beginning)
    if period.end is not None:
        if timestamp and period.end == date.max:
            criteria.append(column <= datetime.max.replace(tzinfo=tz))
        else:
            ending = (datetime.combine(period.end + timedelta(days=1), time.min, tzinfo=tz)
                      if timestamp else period.end)
            criteria.append(column < ending if timestamp else column <= ending)
    return criteria


def dashboard_audience(user: User) -> str:
    """A regra de audiência não herda automaticamente o acesso amplo do ADM."""
    role = (user.role or "").strip().lower()
    if role in {"gestao", "super_admin"}:
        return "gestao"
    if role == "admin":
        return "admin"
    if role in {"lab", "tecnico", "laboratorio"}:
        return "lab"
    if role == "compras" or (role not in {"admin", "gestao", "super_admin"}
                              and user_has_module(role, user.modules, MODULE_PURCHASING)
                              and not user_has_module(role, user.modules, MODULE_LABORATORY)):
        return "compras"
    if role == "estoque" or user_has_module(role, user.modules, MODULE_INVENTORY):
        return "estoque"
    return "outros"


def _due_label(delivery_date: date, today: date) -> str:
    days = (delivery_date - today).days
    if days < 0:
        return f"Atrasada há {-days} dia{'s' if -days != 1 else ''}"
    if days == 0:
        return "Entrega prevista para hoje"
    return f"Entrega em {days} dia{'s' if days != 1 else ''}"


def _purchase_message(purchase: PurchaseOrder) -> str:
    parts = [purchase.product_name]
    if purchase.equipment_serial:
        parts.append(f"Série {purchase.equipment_serial}")
    if purchase.client_destination:
        parts.append(f"Destino: {purchase.client_destination}")
    return " · ".join(parts)


def _os_item(order: LaboratoryWorkOrder, status_label: str, tab: str = "general") -> WorkItem:
    equipment = order.equipment
    name = " ".join(filter(None, [getattr(equipment, "manufacturer", None), getattr(equipment, "model", None)]))
    name = name or getattr(equipment, "name", None) or getattr(equipment, "equipment_type", None) or "Equipamento"
    return WorkItem(
        id=order.id, title=f"OS {order.number.removeprefix('OS-')}",
        description=name,
        meta=order.customer_name,
        status=status_label,
        target=f"/laboratorio?os={order.id}&aba={tab}",
        date_label=f"Entrada {order.opened_at.strftime('%d/%m/%Y')}" if order.opened_at else None,
    )


async def _os_queue(db: AsyncSession, *, key: str, title: str, description: str,
                    tone: str, statuses: tuple[str, ...], status_label: str,
                    tab: str = "general", require_unquoted: bool = False,
                    period: DashboardPeriod | None = None) -> WorkQueue:
    criteria = [LaboratoryWorkOrder.is_cancelled.is_(False),
                LaboratoryWorkOrder.is_inactive.is_(False),
                LaboratoryWorkOrder.status.in_(statuses)]
    criteria.extend(period_criteria(LaboratoryWorkOrder.opened_at, period or DashboardPeriod()))
    if require_unquoted:
        # Um orçamento já emitido não deve aparecer como "falta fazer".
        criteria.append(~exists(select(LaboratoryQuote.id).where(
            LaboratoryQuote.work_order_id == LaboratoryWorkOrder.id,
            LaboratoryQuote.emitted_at.is_not(None),
        )))
    count = int(await db.scalar(select(func.count(LaboratoryWorkOrder.id)).where(*criteria)) or 0)
    rows = list((await db.scalars(select(LaboratoryWorkOrder).options(
                  joinedload(LaboratoryWorkOrder.equipment), raiseload("*"),
                  ).where(*criteria)
                  .order_by(LaboratoryWorkOrder.opened_at.asc(), LaboratoryWorkOrder.id.asc())
                  .limit(5))).all())
    return WorkQueue(key=key, section="orcamentos" if require_unquoted else "laboratorio",
                     title=title, description=description, tone=tone, total=count,
                     target="/laboratorio" if not require_unquoted else "/laboratorio?aba=orcamentos",
                     items=[_os_item(row, status_label, tab) for row in rows])


_REQUEST_LABELS = {
    "awaiting_approval": "Aguardando aprovação", "approved": "Aprovado para compra",
    "purchasing": "Em compra", "purchased": "Comprado",
    "in_transit": "Em trânsito", "received": "Recebido no estoque",
}


async def _materials_queue(db: AsyncSession, *, key: str, title: str,
                           description: str, statuses: tuple[str, ...], tone: str,
                           target: str = "/compras?view=requests",
                           period: DashboardPeriod | None = None) -> WorkQueue:
    criteria = [MaterialRequest.status.in_(statuses),
                *period_criteria(MaterialRequest.created_at, period or DashboardPeriod(), timestamp=True)]
    total = int(await db.scalar(select(func.count(MaterialRequest.id)).where(*criteria)) or 0)
    rows = list((await db.scalars(select(MaterialRequest).where(*criteria)
                .order_by(MaterialRequest.created_at.asc(), MaterialRequest.id.asc())
                .limit(5))).all())
    order_ids = {row.work_order_id for row in rows if row.work_order_id is not None}
    order_numbers = {row.id: row.number for row in (await db.scalars(
        select(LaboratoryWorkOrder).options(
            load_only(LaboratoryWorkOrder.id, LaboratoryWorkOrder.number), raiseload("*"),
        ).where(LaboratoryWorkOrder.id.in_(order_ids))
    )).all()} if order_ids else {}
    return WorkQueue(key=key, section="compras", title=title, description=description,
                     tone=tone, total=total, target=target,
                     items=[WorkItem(id=row.id, title=f"{row.code} · {row.item_name}",
                        description=f"{row.quantity} un. · {order_numbers.get(row.work_order_id, 'Sem OS vinculada')}",
                        meta=None, status=_REQUEST_LABELS.get(row.status, row.status),
                        target=f"{target}{'&' if "?" in target else '?'}solicitacao={row.id}" if target.startswith("/compras") else target,
                        date_label=f"Solicitado em {row.created_at.strftime('%d/%m/%Y')}" if row.created_at else None)
                        for row in rows])


async def _finance_queue(db: AsyncSession, *, key: str, title: str,
                         description: str, tone: str, today: date, overdue: bool,
                         period: DashboardPeriod | None = None) -> WorkQueue:
    criteria = [FinancialEntry.is_deleted.is_(False), FinancialEntry.status == "pending"]
    criteria.append(FinancialEntry.due_date < today if overdue else FinancialEntry.due_date >= today)
    criteria.extend(period_criteria(FinancialEntry.due_date, period or DashboardPeriod()))
    total = int(await db.scalar(select(func.count(FinancialEntry.id)).where(*criteria)) or 0)
    rows = list((await db.scalars(select(FinancialEntry).where(*criteria)
                .order_by(FinancialEntry.due_date.asc(), FinancialEntry.id.asc())
                .limit(5))).all())
    return WorkQueue(key=key, section="financeiro", title=title, description=description,
                     tone=tone, total=total, target="/financeiro",
                     items=[WorkItem(id=row.id, title=row.counterparty_name,
                        description=row.description,
                        status="A receber" if row.entry_type == "income" else "A pagar",
                        meta=f"R$ {row.amount:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
                        target=f"/financeiro?lancamento={row.id}",
                        date_label=f"Venc. {row.due_date.strftime('%d/%m/%Y')}")
                        for row in rows])


async def _invoiced_queue(db: AsyncSession, today: date,
                          period: DashboardPeriod | None = None) -> WorkQueue:
    active_period = period or DashboardPeriod()
    recent_cutoff = today - timedelta(days=30)
    criteria = [LaboratoryWorkOrder.is_cancelled.is_(False),
                LaboratoryWorkOrder.invoiced_at.is_not(None)]
    if active_period.active:
        criteria.extend(period_criteria(LaboratoryWorkOrder.invoiced_at, active_period, timestamp=True))
    else:
        criteria.extend(period_criteria(LaboratoryWorkOrder.invoiced_at,
            DashboardPeriod(start=recent_cutoff), timestamp=True))
    total = int(await db.scalar(select(func.count(LaboratoryWorkOrder.id)).where(*criteria)) or 0)
    rows = list((await db.scalars(select(LaboratoryWorkOrder).options(
        joinedload(LaboratoryWorkOrder.equipment), raiseload("*"),
    ).where(*criteria).order_by(LaboratoryWorkOrder.invoiced_at.desc()).limit(5))).all())
    result = [_os_item(row, "Faturado", "financial") for row in rows]
    for item, order in zip(result, rows):
        item.date_label = f"Faturado em {order.invoiced_at.strftime('%d/%m/%Y')}"
    return WorkQueue(key="recent_invoices", section="financeiro",
                     title="Últimos faturados", description=(
                         f"OS faturadas · {active_period.label}" if active_period.active
                         else "Últimas OS faturadas · últimos 30 dias"),
                     tone="success", total=total, target="/financeiro",
                     items=result)


async def build_summary(user: User, db: AsyncSession,
                        period: DashboardPeriod | None = None) -> DashboardSummary:
    now = datetime.now(ZoneInfo("America/Recife"))
    today = now.date()
    period = period or DashboardPeriod()
    due_limit = today + timedelta(days=7)
    month_start = today.replace(day=1)
    month_label = f"{_MONTHS[now.month - 1]} de {now.year}"
    audience = dashboard_audience(user)

    visible_lab = audience in {"gestao", "lab"}
    visible_quotes = audience in {"gestao", "admin"} and user_can_create_quote(user.role, user.modules)
    visible_purchases = audience in {"gestao", "compras"}
    visible_finance = audience == "gestao"  # barreira antes de fazer qualquer consulta financeira
    visible_stock = audience == "estoque"
    queues: list[WorkQueue] = []

    monthly_equipment_count = 0
    if visible_lab or visible_quotes:
        if visible_lab:
            queues.append(await _os_queue(db, key="lab_entries", title="Equipamentos em entrada",
                description="Recebidos ou aguardando análise técnica",
                tone="info", statuses=("received", "awaiting_analysis"), status_label="Entrada", period=period))
            queues.append(await _os_queue(db, key="lab_approved", title="Serviços aprovados",
                description="OS aprovadas que aguardam continuidade no laboratório",
                tone="success", statuses=("approved",), status_label="Aprovado", tab="technical", period=period))
            monthly_criteria = [LaboratoryWorkOrder.is_cancelled.is_(False)]
            monthly_criteria.extend(period_criteria(LaboratoryWorkOrder.opened_at, period)
                if period.active else [LaboratoryWorkOrder.opened_at >= month_start])
            monthly_equipment_count = int(await db.scalar(select(func.count(LaboratoryWorkOrder.id)).where(
                *monthly_criteria,
            )) or 0)
        if visible_quotes:
            queues.append(await _os_queue(db, key="quotes_pending", title="Orçamentos a elaborar",
                description="Equipamentos analisados ainda sem orçamento emitido",
                tone="warning", statuses=("in_analysis", "awaiting_quote"),
                status_label="Analisado", tab="quote", require_unquoted=True, period=period))

    purchases: list[PurchaseOrder] = []
    if visible_purchases:
        queues.extend([
            await _materials_queue(db, key="requests_approval", title="Solicitações para aprovar",
                description="Materiais aguardando autorização", tone="warning", statuses=("awaiting_approval",), period=period),
            await _materials_queue(db, key="requests_buy", title="Materiais para comprar",
                description="Solicitações aprovadas que ainda precisam ser compradas", tone="info",
                statuses=("approved", "purchasing"), period=period),
            await _materials_queue(db, key="requests_arrival", title="Aguardando chegada",
                description="Materiais comprados e ainda não recebidos", tone="danger",
                statuses=("purchased", "in_transit"), period=period),
        ])
        purchases = list((await db.scalars(select(PurchaseOrder).where(
            PurchaseOrder.is_deleted.is_(False),
            PurchaseOrder.status.in_(_OPEN_PURCHASE_STATUSES),
            PurchaseOrder.estimated_delivery_date <= due_limit,
            *period_criteria(PurchaseOrder.purchase_date, period),
        ).order_by(PurchaseOrder.estimated_delivery_date, PurchaseOrder.id.desc()).limit(30))).all())

    if visible_stock:
        stock_queue = await _materials_queue(db, key="stock_to_receive", title="Materiais a receber",
            description="Comprados e em trânsito, aguardando entrada física no estoque",
            tone="warning", statuses=("purchased", "in_transit"), target="/estoque", period=period)
        stock_queue.section = "estoque"
        queues.append(stock_queue)
        stock_ready = await _materials_queue(db, key="stock_to_deliver", title="Separar para o laboratório",
            description="Itens recebidos que aguardam entrega ao laboratório",
            tone="success", statuses=("received",), target="/estoque", period=period)
        stock_ready.section = "estoque"
        queues.append(stock_ready)

    if visible_finance:
        queues.extend([
            await _finance_queue(db, key="finance_overdue", title="Financeiro em atraso",
                description="Recebimentos e pagamentos com vencimento ultrapassado",
                tone="danger", today=today, overdue=True, period=period),
            await _finance_queue(db, key="finance_pending", title="Financeiro pendente",
                description="Lançamentos a receber e pagar ainda no prazo",
                tone="warning", today=today, overdue=False, period=period),
            await _invoiced_queue(db, today, period=period),
        ])

    overdue = [item for item in purchases if item.estimated_delivery_date < today]
    due_soon = [item for item in purchases if today <= item.estimated_delivery_date <= due_limit]
    unread_notifications = int(await db.scalar(select(func.count(Notification.id)).where(
        Notification.user_id == user.id,
        Notification.is_read.is_(False),
    )) or 0)

    alerts = [Alert(key="unread_notifications", label="Notificações não lidas",
                    value=unread_notifications, detail="Abrir central de notificações",
                    tone="warning" if unread_notifications else "info", target="/notificacoes")]
    if visible_quotes:
        alerts.append(Alert(key="quotes_pending", label="Orçamentos a fazer",
                            value=next(q.total for q in queues if q.key == "quotes_pending"),
                            detail="Ver equipamentos analisados", tone="warning",
                            target="/laboratorio?aba=orcamentos"))
    if visible_lab:
        alerts.extend([
            Alert(key="lab_entries", label="Novas entradas",
                  value=next(q.total for q in queues if q.key == "lab_entries"),
                  detail="Ver equipamentos aguardando análise", tone="info", target="/laboratorio"),
            Alert(key="lab_approved", label="OS aprovadas",
                  value=next(q.total for q in queues if q.key == "lab_approved"),
                  detail="Continuar serviços autorizados", tone="warning", target="/laboratorio"),
        ])
    if visible_purchases:
        alerts.extend([
            Alert(key="requests_buy", label="Solicitações para comprar",
                  value=next(q.total for q in queues if q.key == "requests_buy"),
                  detail="Abrir solicitações", tone="warning", target="/compras?view=requests"),
            Alert(key="delayed_purchases", label="Pedidos atrasados",
                  value=len(overdue), detail="Acompanhar atrasos",
                  tone="danger" if overdue else "info", target="/compras?filtro=atrasados"),
        ])
    if visible_finance:
        alerts.append(Alert(key="finance_overdue", label="Financeiro em atraso",
                            value=next(q.total for q in queues if q.key == "finance_overdue"),
                            detail="Conferir lançamentos", tone="danger", target="/financeiro"))

    quick_actions: list[QuickAction] = []
    if visible_lab:
        quick_actions.append(QuickAction(key="new_work_order", label="Criar nova OS",
            description="Registrar entrada no laboratório", target="/laboratorio?acao=nova-os"))
    if visible_quotes:
        quick_actions.append(QuickAction(key="new_budget", label="Fazer orçamento",
            description="Ver OS analisadas", target="/laboratorio?aba=orcamentos"))
    if visible_stock or visible_purchases or audience == "gestao":
        quick_actions.append(QuickAction(key="unnoted_movement", label="Movimentar estoque",
            description="Registrar movimentação sem nota", target="/estoque/movimentos/sem-nota/novo"))

    events = [PurchaseEvent(
        id=purchase.id, code=purchase.code, supplier=purchase.supplier_name,
        message=_purchase_message(purchase),
        due_label=_due_label(purchase.estimated_delivery_date, today),
        status="overdue" if purchase.estimated_delivery_date < today else "due_soon",
        target=f"/compras?pedido={purchase.id}",
    ) for purchase in purchases]

    return DashboardSummary(audience=audience, alerts=alerts, work_queues=queues,
        purchase_events=events, quick_actions=quick_actions,
        monthly_equipment_entries=MonthlyEquipmentEntries(
            month_label=period.label if period.active else month_label, count=monthly_equipment_count),
        filtered_period=period.active)
