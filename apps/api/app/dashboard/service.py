from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.access import MODULE_FINANCE, MODULE_LABORATORY, MODULE_PURCHASING, user_can_create_quote, user_has_module
from app.auth.models import User
from app.dashboard.schemas import (
    Alert,
    DashboardSummary,
    MonthlyEquipmentEntries,
    PurchaseEvent,
    QuickAction,
)
from app.finance.models import FinancialEntry
from app.laboratory.models import LaboratoryWorkOrder
from app.notifications.models import Notification
from app.laboratory.service import TERMINAL_STATUSES
from app.purchasing.models import PurchaseOrder

_MONTHS = (
    "janeiro",
    "fevereiro",
    "março",
    "abril",
    "maio",
    "junho",
    "julho",
    "agosto",
    "setembro",
    "outubro",
    "novembro",
    "dezembro",
)
_OPEN_PURCHASE_STATUSES = (
    "awaiting_payment",
    "ordered",
    "processing",
    "shipped",
    "customs",
)


def _due_label(delivery_date: date, today: date) -> str:
    days = (delivery_date - today).days
    if days < 0:
        amount = abs(days)
        return f"Atrasada há {amount} dia{'s' if amount != 1 else ''}"
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


async def build_summary(user: User, db: AsyncSession) -> DashboardSummary:
    now = datetime.now(ZoneInfo("America/Recife"))
    today = now.date()
    due_limit = today + timedelta(days=7)
    month_start = today.replace(day=1)
    month_label = f"{_MONTHS[now.month - 1]} de {now.year}"

    purchases: list[PurchaseOrder] = []
    if user_has_module(user.role, user.modules, MODULE_PURCHASING):
        query = (
            select(PurchaseOrder)
            .where(
                PurchaseOrder.is_deleted.is_(False),
                PurchaseOrder.status.in_(_OPEN_PURCHASE_STATUSES),
                PurchaseOrder.estimated_delivery_date <= due_limit,
            )
            .order_by(PurchaseOrder.estimated_delivery_date, PurchaseOrder.id.desc())
            .limit(30)
        )
        purchases = list((await db.scalars(query)).all())

    overdue = [item for item in purchases if item.estimated_delivery_date < today]
    due_soon = [
        item for item in purchases if today <= item.estimated_delivery_date <= due_limit
    ]

    pending_finance = 0
    if user_has_module(user.role, user.modules, MODULE_FINANCE):
        pending_finance = int(
            await db.scalar(
                select(func.count(FinancialEntry.id)).where(
                    FinancialEntry.is_deleted.is_(False),
                    FinancialEntry.status == "pending",
                )
            )
            or 0
        )

    active_work_orders = 0
    monthly_equipment_count = 0
    if user_has_module(user.role, user.modules, MODULE_LABORATORY):
        active_work_orders = int(
            await db.scalar(
                select(func.count(LaboratoryWorkOrder.id)).where(
                    LaboratoryWorkOrder.is_cancelled.is_(False),
                    LaboratoryWorkOrder.status.notin_(TERMINAL_STATUSES),
                )
            )
            or 0
        )
        monthly_equipment_count = int(
            await db.scalar(
                select(func.count(LaboratoryWorkOrder.id)).where(
                    LaboratoryWorkOrder.is_cancelled.is_(False),
                    LaboratoryWorkOrder.opened_at >= month_start,
                )
            )
            or 0
        )

    unread_notifications = int(
        await db.scalar(
            select(func.count(Notification.id)).where(
                Notification.user_id == user.id,
                Notification.is_read.is_(False),
            )
        )
        or 0
    )

    alerts = [
        Alert(
            key="unread_notifications",
            label="Notificações pendentes",
            value=unread_notifications,
            detail="Abrir central de notificações",
            tone="warning" if unread_notifications else "info",
            target="/painel?notificacoes=1",
        ),
        Alert(
            key="delayed_purchases",
            label="Compras em atraso",
            value=len(overdue),
            detail="Abrir pedidos atrasados",
            tone="danger" if overdue else "info",
            target="/compras?filtro=atrasados",
        ),
        Alert(
            key="purchases_due_soon",
            label="Próximas entregas",
            value=len(due_soon),
            detail="Previsão para até 7 dias",
            tone="warning" if due_soon else "info",
            target="/compras?filtro=proximas",
        ),
        Alert(
            key="active_work_orders",
            label="OS abertas no laboratório",
            value=active_work_orders,
            detail="Abrir ordens em andamento",
            tone="warning" if active_work_orders else "info",
            target="/laboratorio/os",
        ),
        Alert(
            key="pending_finance",
            label="Lançamentos pendentes",
            value=pending_finance,
            detail="Abrir operações financeiras",
            tone="warning" if pending_finance else "info",
            target="/financeiro",
        ),
    ]

    if not user_has_module(user.role, user.modules, MODULE_FINANCE):
        alerts = [alert for alert in alerts if alert.key != "pending_finance"]

    events = [
        PurchaseEvent(
            id=purchase.id,
            code=purchase.code,
            supplier=purchase.supplier_name,
            message=_purchase_message(purchase),
            due_label=_due_label(purchase.estimated_delivery_date, today),
            status="overdue" if purchase.estimated_delivery_date < today else "due_soon",
            target=f"/compras?pedido={purchase.id}",
        )
        for purchase in purchases
    ]

    return DashboardSummary(
        alerts=alerts,
        purchase_events=events,
        quick_actions=[
            QuickAction(
                key="new_work_order",
                label="Criar nova OS",
                description="Entrada de equipamento no laboratório",
                target="/laboratorio/os/nova",
            ),
            *([QuickAction(
                key="new_budget",
                label="Fazer orçamento",
                description="Abrir a área de orçamentos das OS",
                target="/laboratorio/os?aba=orcamentos",
            )] if user_can_create_quote(user.role, user.modules) else []),
            QuickAction(
                key="unnoted_movement",
                label="Documento sem nota",
                description="Registrar entrada ou saída de mercadoria",
                target="/estoque/movimentos/sem-nota/novo",
            ),
        ],
        monthly_equipment_entries=MonthlyEquipmentEntries(
            month_label=month_label,
            count=monthly_equipment_count,
        ),
    )
