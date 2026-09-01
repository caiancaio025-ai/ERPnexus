from datetime import date
import re
from math import ceil

from sqlalchemy import func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.laboratory.models import LaboratoryEquipment, LaboratoryWorkOrder
from app.laboratory.status_flow import WORK_ORDER_STATUSES, can_transition  # noqa: F401

TERMINAL_STATUSES = {"delivered", "invoiced", "cancelled", "no_repair"}


def can_transition_status(current: str, target: str) -> bool:
    return can_transition(current, target)


def normalize_serial(serial: str | None) -> str | None:
    if not serial:
        return None
    return re.sub(r"[^A-Z0-9]", "", serial.upper())


def apply_work_order_update(work_order, payload, *, equipment_id: int) -> None:
    """Aplica os campos editáveis da O.S., incluindo a empresa emissora.

    Mantemos esta atribuição em um único ponto para impedir regressão em que
    ``company_code`` era usado para localizar o equipamento, mas não era salvo
    na própria O.S.
    """
    work_order.company_code = payload.company_code
    work_order.equipment_id = equipment_id
    work_order.customer_id = payload.customer_id
    work_order.customer_name = payload.customer_name.strip()
    work_order.equipment_serial = payload.serial_number
    work_order.priority = payload.priority
    work_order.reported_defect = payload.reported_defect
    work_order.entry_condition = payload.entry_condition
    work_order.accessories_received = payload.accessories_received
    work_order.assigned_technician_id = payload.assigned_technician_id
    work_order.entry_invoice = payload.entry_invoice
    work_order.exit_invoice = payload.exit_invoice
    work_order.parts_cost = payload.parts_cost or None
    work_order.quoted_value = payload.quoted_value or None
    work_order.approved_value = payload.approved_value or None
    work_order.internal_notes = payload.internal_notes
    work_order.customer_notes = payload.customer_notes


async def next_work_order_number(db: AsyncSession) -> str:
    """Gera o próximo número de OS sem regressão após importações legadas.

    A base histórica foi importada com números altos (ex.: OS-30479), enquanto a
    sequence PostgreSQL original podia continuar em 1. Antes de consumir o número,
    sincronizamos a sequence com o maior sufixo numérico já persistido. O advisory
    lock evita duas aberturas concorrentes recalcularem o mesmo intervalo.
    """
    await db.execute(text("SELECT pg_advisory_xact_lock(hashtext('laboratory_work_order_number_seq'))"))
    max_existing = await db.scalar(
        text(
            """
            SELECT COALESCE(MAX(CAST(SUBSTRING(number FROM 4) AS BIGINT)), 0)
            FROM laboratory_work_orders
            WHERE number ~ '^OS-[0-9]+$'
            """
        )
    )
    candidate = await db.scalar(text("SELECT nextval('laboratory_work_order_number_seq')"))
    if candidate is None:
        raise RuntimeError("Não foi possível gerar o número da OS.")

    max_number = int(max_existing or 0)
    number = int(candidate)
    if number <= max_number:
        await db.execute(
            text("SELECT setval('laboratory_work_order_number_seq', :next_number, false)"),
            {"next_number": max_number + 1},
        )
        corrected = await db.scalar(text("SELECT nextval('laboratory_work_order_number_seq')"))
        if corrected is None:
            raise RuntimeError("Não foi possível sincronizar o número da OS.")
        number = int(corrected)

    return f"OS-{number:04d}"


async def find_or_create_equipment(
    db: AsyncSession,
    *,
    company_code: str,
    customer_id: int | None,
    customer_name: str,
    serial_number: str | None,
    manufacturer: str | None,
    model: str | None,
    equipment_type: str | None,
    power: str | None,
    voltage: str | None,
    user_id: int,
) -> LaboratoryEquipment:
    """Reaproveita o cadastro de equipamento existente pelo serial (por empresa);
    se não houver serial ou não encontrar, cria um novo registro."""
    serial_normalized = normalize_serial(serial_number)
    equipment = None
    if serial_normalized:
        equipment = await db.scalar(
            select(LaboratoryEquipment).where(
                LaboratoryEquipment.company_code == company_code,
                LaboratoryEquipment.serial_normalized == serial_normalized,
            )
        )
    if equipment:
        equipment.customer_id = customer_id
        equipment.customer_name = customer_name
        equipment.manufacturer = manufacturer or equipment.manufacturer
        equipment.model = model or equipment.model
        equipment.equipment_type = equipment_type or equipment.equipment_type
        equipment.power = power or equipment.power
        equipment.voltage = voltage or equipment.voltage
        return equipment

    equipment = LaboratoryEquipment(
        company_code=company_code,
        customer_id=customer_id,
        customer_name=customer_name,
        serial_number=serial_number,
        serial_normalized=serial_normalized,
        manufacturer=manufacturer,
        model=model,
        equipment_type=equipment_type,
        power=power,
        voltage=voltage,
        created_by=user_id,
    )
    db.add(equipment)
    await db.flush()
    return equipment


async def list_work_orders_page(
    db: AsyncSession,
    *,
    page: int,
    page_size: int,
    company_code: str | None = None,
    status: str | None = None,
    search: str | None = None,
    opened_from: date | None = None,
    opened_before: date | None = None,
) -> tuple[list[LaboratoryWorkOrder], int]:
    filters = []
    if status:
        filters.append(LaboratoryWorkOrder.status == status)
    if company_code:
        filters.append(LaboratoryWorkOrder.company_code == company_code)
    if opened_from is not None:
        filters.append(LaboratoryWorkOrder.opened_at >= opened_from)
    if opened_before is not None:
        filters.append(LaboratoryWorkOrder.opened_at < opened_before)
    if search:
        term = f"%{search.strip()}%"
        filters.append(
            or_(
                LaboratoryWorkOrder.number.ilike(term),
                LaboratoryWorkOrder.customer_name.ilike(term),
                LaboratoryWorkOrder.equipment_serial.ilike(term),
                LaboratoryWorkOrder.entry_invoice.ilike(term),
                LaboratoryWorkOrder.exit_invoice.ilike(term),
            )
        )

    total = int(await db.scalar(select(func.count(LaboratoryWorkOrder.id)).where(*filters)) or 0)
    offset = (page - 1) * page_size
    query = (
        select(LaboratoryWorkOrder)
        .where(*filters)
        .order_by(LaboratoryWorkOrder.opened_at.desc(), LaboratoryWorkOrder.id.desc())
        .offset(offset)
        .limit(page_size)
    )
    work_orders = list((await db.scalars(query)).all())
    return work_orders, total


def total_pages(total: int, page_size: int) -> int:
    return ceil(total / page_size) if total else 0


SUMMARY_FIELDS = (
    "total_open",
    "analyzed",
    "awaiting_approval",
    "approved",
    "awaiting_analysis",
    "in_repair",
    "in_testing",
    "high_priority",
    "completed_month",
)


async def work_order_period_range(
    db: AsyncSession,
    *,
    company_code: str | None = None,
) -> tuple[date | None, date | None]:
    """Return latest/earliest opening dates with a single database round-trip."""
    filters = []
    if company_code:
        filters.append(LaboratoryWorkOrder.company_code == company_code)

    statement = select(
        func.max(LaboratoryWorkOrder.opened_at).label("latest"),
        func.min(LaboratoryWorkOrder.opened_at).label("earliest"),
    ).where(*filters)
    row = (await db.execute(statement)).one()
    return row.latest, row.earliest


async def work_order_summary_counts(
    db: AsyncSession,
    *,
    company_code: str | None = None,
    opened_from: date | None = None,
    opened_before: date | None = None,
    completed_from: date,
) -> dict[str, int]:
    """Build every Laboratory summary KPI in one aggregate query.

    ``opened_from``/``opened_before`` scope every KPI exactly like the legacy
    endpoint. ``completed_from`` only adds the historical current-month
    completion condition used by ``completed_month``.
    """
    filters = []
    if company_code:
        filters.append(LaboratoryWorkOrder.company_code == company_code)
    if opened_from is not None:
        filters.append(LaboratoryWorkOrder.opened_at >= opened_from)
    if opened_before is not None:
        filters.append(LaboratoryWorkOrder.opened_at < opened_before)

    statement = select(
        func.count(LaboratoryWorkOrder.id)
        .filter(LaboratoryWorkOrder.status.notin_(TERMINAL_STATUSES))
        .label("total_open"),
        func.count(LaboratoryWorkOrder.id)
        .filter(LaboratoryWorkOrder.status == "in_analysis")
        .label("analyzed"),
        func.count(LaboratoryWorkOrder.id)
        .filter(LaboratoryWorkOrder.status == "awaiting_approval")
        .label("awaiting_approval"),
        func.count(LaboratoryWorkOrder.id)
        .filter(LaboratoryWorkOrder.status == "approved")
        .label("approved"),
        func.count(LaboratoryWorkOrder.id)
        .filter(LaboratoryWorkOrder.status.in_(("received", "awaiting_analysis")))
        .label("awaiting_analysis"),
        func.count(LaboratoryWorkOrder.id)
        .filter(LaboratoryWorkOrder.status == "in_repair")
        .label("in_repair"),
        func.count(LaboratoryWorkOrder.id)
        .filter(LaboratoryWorkOrder.status == "in_testing")
        .label("in_testing"),
        func.count(LaboratoryWorkOrder.id)
        .filter(
            LaboratoryWorkOrder.priority.in_(("high", "urgent")),
            LaboratoryWorkOrder.status.notin_(TERMINAL_STATUSES),
        )
        .label("high_priority"),
        func.count(LaboratoryWorkOrder.id)
        .filter(
            LaboratoryWorkOrder.status.in_(("completed", "delivered")),
            LaboratoryWorkOrder.completed_at >= completed_from,
        )
        .label("completed_month"),
        func.coalesce(
            func.sum(LaboratoryWorkOrder.approved_value).filter(
                LaboratoryWorkOrder.status == "approved"
            ),
            0,
        ).label("approved_total"),
        func.coalesce(
            func.sum(LaboratoryWorkOrder.quoted_value).filter(
                LaboratoryWorkOrder.status == "awaiting_approval"
            ),
            0,
        ).label("awaiting_approval_total"),
    ).where(*filters)

    row = (await db.execute(statement)).one()

    result = {
        field: int(getattr(row, field) or 0)
        for field in SUMMARY_FIELDS
    }
    result["approved_total"] = row.approved_total or 0
    result["awaiting_approval_total"] = row.awaiting_approval_total or 0
    return result
