from datetime import UTC, date, datetime
import re
from math import ceil

from sqlalchemy import exists, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.laboratory.models import (
    LaboratoryArea,
    LaboratoryEquipment,
    LaboratoryLocation,
    LaboratoryLocationHistory,
    LaboratoryRack,
    LaboratoryWorkOrder,
    LaboratoryWorkOrderSubstatus,
)
from app.laboratory.status_flow import WORK_ORDER_STATUSES, can_transition  # noqa: F401

TERMINAL_STATUSES = {"delivered", "invoiced", "cancelled", "no_repair"}

# Compatibilidade de leitura para contratos antigos. A fonte de verdade passa
# a ser laboratory_areas / laboratory_racks / laboratory_locations.
LAB_RACKS: tuple[tuple[str, str], ...] = (
    ("E1", "A"), ("E2", "B"), ("E3", "C"),
    ("E4", "D"), ("E5", "E"), ("E6", "F"),
)
LAB_RACK_SLOT_COUNT = 6
LAB_PHYSICAL_LOCATIONS: tuple[str, ...] = tuple(
    f"{letter}{slot}" for _, letter in LAB_RACKS for slot in range(1, LAB_RACK_SLOT_COUNT + 1)
)


async def active_physical_locations(db: AsyncSession) -> list[str]:
    rows = list((await db.execute(
        select(LaboratoryLocation.code)
        .join(LaboratoryArea, LaboratoryArea.id == LaboratoryLocation.area_id)
        .outerjoin(LaboratoryRack, LaboratoryRack.id == LaboratoryLocation.rack_id)
        .where(
            LaboratoryLocation.is_active.is_(True),
            LaboratoryArea.is_active.is_(True),
            or_(LaboratoryRack.id.is_(None), LaboratoryRack.is_active.is_(True)),
        )
        .order_by(
            LaboratoryArea.sort_order,
            func.coalesce(LaboratoryRack.sort_order, -1),
            LaboratoryLocation.sort_order,
            LaboratoryLocation.code,
        )
    )).all())
    return [str(row[0]) for row in rows]


def group_work_orders_by_location(work_orders) -> dict[str, list[LaboratoryWorkOrder]]:
    grouped: dict[str, list[LaboratoryWorkOrder]] = {}
    for work_order in work_orders:
        location = normalize_storage_location(getattr(work_order, "storage_location", None))
        if not location:
            continue
        grouped.setdefault(location, []).append(work_order)
    return grouped


def can_transition_status(current: str, target: str) -> bool:
    return can_transition(current, target)


def normalize_storage_location(value: str | None) -> str | None:
    if not value:
        return None
    return value.strip().upper().replace(" ", "")


async def ensure_storage_location_available(
    db: AsyncSession, location: str | None, *, exclude_work_order_id: int | None = None
) -> None:
    """Valida existência da localização configurada.

    A posição pode ter várias O.S.; não existe unicidade por ocupação.
    """
    _ = exclude_work_order_id
    normalized = normalize_storage_location(location)
    if not normalized:
        return
    exists_location = await db.scalar(
        select(LaboratoryLocation.id)
        .join(LaboratoryArea, LaboratoryArea.id == LaboratoryLocation.area_id)
        .outerjoin(LaboratoryRack, LaboratoryRack.id == LaboratoryLocation.rack_id)
        .where(
            LaboratoryLocation.code == normalized,
            LaboratoryLocation.is_active.is_(True),
            LaboratoryArea.is_active.is_(True),
            or_(LaboratoryRack.id.is_(None), LaboratoryRack.is_active.is_(True)),
        )
        .limit(1)
    )
    if exists_location is None:
        raise ValueError("Localização física inexistente ou inativa. Selecione uma localização cadastrada.")


async def set_storage_location(
    db: AsyncSession, work_order: LaboratoryWorkOrder, location: str | None, user_id: int
) -> None:
    normalized = normalize_storage_location(location)
    current = normalize_storage_location(work_order.storage_location)
    if normalized == current:
        return
    await ensure_storage_location_available(db, normalized, exclude_work_order_id=work_order.id)
    if current:
        active_history = await db.scalar(
            select(LaboratoryLocationHistory)
            .where(
                LaboratoryLocationHistory.work_order_id == work_order.id,
                LaboratoryLocationHistory.released_at.is_(None),
            )
            .order_by(LaboratoryLocationHistory.id.desc())
            .limit(1)
        )
        if active_history is not None:
            active_history.released_at = datetime.now(UTC)
    work_order.storage_location = normalized
    if normalized:
        db.add(LaboratoryLocationHistory(
            work_order_id=work_order.id,
            location=normalized,
            changed_by=user_id,
        ))


async def next_free_storage_location(db: AsyncSession) -> str:
    """Sugere a localização ativa menos carregada, respeitando a ordem configurada."""
    locations = await active_physical_locations(db)
    if not locations:
        raise ValueError("Nenhuma localização física ativa foi cadastrada.")
    rows = (
        await db.execute(
            select(LaboratoryWorkOrder.storage_location, func.count(LaboratoryWorkOrder.id))
            .where(LaboratoryWorkOrder.storage_location.in_(locations), LaboratoryWorkOrder.is_inactive.is_(False))
            .group_by(LaboratoryWorkOrder.storage_location)
        )
    ).all()
    counts = {normalize_storage_location(location): int(count) for location, count in rows if location}
    order = {location: index for index, location in enumerate(locations)}
    return min(locations, key=lambda location: (counts.get(location, 0), order[location]))


def normalize_serial(serial: str | None) -> str | None:
    if not serial:
        return None
    return re.sub(r"[^A-Z0-9]", "", serial.upper())


def apply_work_order_update(
    work_order,
    payload,
    *,
    equipment_id: int,
    include_sensitive_values: bool = True,
) -> None:
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
    work_order.entry_invoice_2 = payload.entry_invoice_2
    work_order.entry_invoice_3 = payload.entry_invoice_3
    work_order.entry_invoice_access_key = payload.entry_invoice_access_key
    work_order.exit_invoice = payload.exit_invoice
    work_order.exit_invoice_2 = payload.exit_invoice_2
    work_order.exit_invoice_3 = payload.exit_invoice_3
    work_order.exit_invoice_access_key = payload.exit_invoice_access_key
    work_order.warranty_invoice = payload.warranty_invoice
    work_order.warranty_invoice_2 = payload.warranty_invoice_2
    work_order.warranty_invoice_3 = payload.warranty_invoice_3
    work_order.warranty_entry_invoice_1 = payload.warranty_entry_invoice_1
    work_order.warranty_entry_invoice_2 = payload.warranty_entry_invoice_2
    work_order.warranty_entry_invoice_3 = payload.warranty_entry_invoice_3
    work_order.warranty_exit_invoice_1 = payload.warranty_exit_invoice_1
    work_order.warranty_exit_invoice_2 = payload.warranty_exit_invoice_2
    work_order.warranty_exit_invoice_3 = payload.warranty_exit_invoice_3
    if include_sensitive_values:
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
    include_inactive: bool = False,
) -> tuple[list[LaboratoryWorkOrder], int]:
    filters = [] if include_inactive else [LaboratoryWorkOrder.is_inactive.is_(False)]
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
                LaboratoryWorkOrder.entry_invoice_2.ilike(term),
                LaboratoryWorkOrder.entry_invoice_3.ilike(term),
                LaboratoryWorkOrder.entry_invoice_access_key.ilike(term),
                LaboratoryWorkOrder.exit_invoice.ilike(term),
                LaboratoryWorkOrder.exit_invoice_2.ilike(term),
                LaboratoryWorkOrder.exit_invoice_3.ilike(term),
                LaboratoryWorkOrder.exit_invoice_access_key.ilike(term),
                LaboratoryWorkOrder.warranty_invoice.ilike(term),
                LaboratoryWorkOrder.warranty_invoice_2.ilike(term),
                LaboratoryWorkOrder.warranty_invoice_3.ilike(term),
                LaboratoryWorkOrder.warranty_entry_invoice_1.ilike(term),
                LaboratoryWorkOrder.warranty_entry_invoice_2.ilike(term),
                LaboratoryWorkOrder.warranty_entry_invoice_3.ilike(term),
                LaboratoryWorkOrder.warranty_exit_invoice_1.ilike(term),
                LaboratoryWorkOrder.warranty_exit_invoice_2.ilike(term),
                LaboratoryWorkOrder.warranty_exit_invoice_3.ilike(term),
                LaboratoryWorkOrder.storage_location.ilike(term),
                LaboratoryWorkOrder.equipment.has(
                    or_(
                        LaboratoryEquipment.equipment_type.ilike(term),
                        LaboratoryEquipment.manufacturer.ilike(term),
                        LaboratoryEquipment.model.ilike(term),
                        func.concat_ws(
                            " ",
                            LaboratoryEquipment.equipment_type,
                            LaboratoryEquipment.manufacturer,
                            LaboratoryEquipment.model,
                        ).ilike(term),
                    )
                ),
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
    filters = [LaboratoryWorkOrder.is_inactive.is_(False)]
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
    completed_before: date | None = None,
) -> dict[str, int]:
    """Build every Laboratory summary KPI in one aggregate query.

    ``opened_from``/``opened_before`` scope every KPI exactly like the legacy
    endpoint. ``completed_from`` only adds the historical current-month
    completion condition used by ``completed_month``.
    """
    filters = [LaboratoryWorkOrder.is_inactive.is_(False)]
    if company_code:
        filters.append(LaboratoryWorkOrder.company_code == company_code)
    if opened_from is not None:
        filters.append(LaboratoryWorkOrder.opened_at >= opened_from)
    if opened_before is not None:
        filters.append(LaboratoryWorkOrder.opened_at < opened_before)

    completed_filters = [LaboratoryWorkOrder.completed_at >= completed_from]
    if completed_before is not None:
        completed_filters.append(LaboratoryWorkOrder.completed_at < completed_before)

    delivered_substatus_active = exists(
        select(1).where(
            LaboratoryWorkOrderSubstatus.work_order_id == LaboratoryWorkOrder.id,
            LaboratoryWorkOrderSubstatus.code == "delivered",
            LaboratoryWorkOrderSubstatus.is_active.is_(True),
        )
    )
    open_work_order = (
        LaboratoryWorkOrder.status.notin_(TERMINAL_STATUSES)
        & ~delivered_substatus_active
    )

    statement = select(
        func.count(LaboratoryWorkOrder.id)
        .filter(open_work_order)
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
            open_work_order,
        )
        .label("high_priority"),
        func.count(LaboratoryWorkOrder.id)
        .filter(*completed_filters)
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
