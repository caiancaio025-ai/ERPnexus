"""Endpoints de localização, estoque, fotos, etiquetas e consumo vinculado à OS."""
import asyncio
from collections import defaultdict
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, Response
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.access import user_can_view_sensitive_values
from app.auth.dependencies import require_any_module, require_module
from app.auth.models import User
from app.auth.router import current_user
from app.core.config import settings
from app.core.db import get_db
from app.core.file_validation import InvalidUpload
from app.core.upload_stream import UploadTooLarge, persist_streamed_upload
from app.commercial.models import CommercialCompanyProfile
from app.inventory.stock_codes import format_stock_code, stock_id_from_query
from app.inventory.label_pdf import inventory_label_pdf
from app.inventory.models import (
    InventoryArea, InventoryComponentCategory, InventoryComponentSubtype, InventoryComponentFormat, InventoryContainer, InventoryItem, InventoryLocationHistory, InventoryLocationType,
    InventoryMovement, InventoryPhoto, InventorySlot,
)
from app.inventory.schemas import AreaInput, CategoryInput, ContainerInput, ContainerUpdate, FormatInput, ItemInput, ItemUpdate, MovementInput, SubtypeInput, TypeInput
from app.inventory.service import move_stock
from app.inventory.drawer_batch import missing_drawer_numbers

router = APIRouter(prefix="/inventory", dependencies=[Depends(require_any_module("estoque", "laboratorio"))])
STORAGE = Path(settings.storage_root) / "inventory"
DB = Depends(get_db)
USER = Depends(current_user)


def _money_allowed(user: User) -> bool:
    return user_can_view_sensitive_values(user.role)


def _model(obj) -> dict:
    return {col.name: getattr(obj, col.name) for col in obj.__table__.columns}


def _item_dict(obj: InventoryItem, user: User, slot: str | None = None, photo_ids: list[int] | None = None) -> dict:
    data = _model(obj)
    if not _money_allowed(user):
        data.pop("unit_cost", None)
    data["location_code"] = slot
    data["photo_ids"] = photo_ids or []
    return data


def _readable_location(code: str) -> str:
    """Endereço de fácil leitura para a etiqueta PDF, sem mudar a chave do slot."""
    import re

    if re.fullmatch(r"[A-Z]{1,3}[1-5]", code):
        return f"Estante {code}"
    for prefix, name in (("CAIXA-", "Caixa"), ("GAVETA-", "Gaveta"), ("GALERIA-", "Galeia")):
        if code.startswith(prefix):
            return f"{name} {code[len(prefix):]}"
    return code


async def _valid_slot(db: AsyncSession, slot_id: int | None) -> None:
    if slot_id is not None:
        slot = await db.get(InventorySlot, slot_id)
        if slot is None or not slot.is_active:
            raise HTTPException(422, "Posição de estoque inválida.")
        container = await db.get(InventoryContainer, slot.container_id)
        if container is None or not container.is_active:
            raise HTTPException(422, "Local de estoque inativo.")


@router.get("/map")
async def inventory_map(db: AsyncSession = DB):
    areas = (await db.scalars(select(InventoryArea).order_by(InventoryArea.code))).all()
    types = (await db.scalars(select(InventoryLocationType).order_by(InventoryLocationType.name))).all()
    categories = (await db.scalars(select(InventoryComponentCategory).order_by(InventoryComponentCategory.name))).all()
    subtypes = (await db.scalars(select(InventoryComponentSubtype).order_by(InventoryComponentSubtype.category, InventoryComponentSubtype.name))).all()
    formats = (await db.scalars(select(InventoryComponentFormat).order_by(InventoryComponentFormat.category, InventoryComponentFormat.name))).all()
    containers = (await db.scalars(select(InventoryContainer).order_by(InventoryContainer.layout_row, InventoryContainer.layout_column, InventoryContainer.code))).all()
    slots = (await db.scalars(select(InventorySlot).order_by(InventorySlot.row, InventorySlot.column))).all()
    items = (await db.scalars(select(InventoryItem).where(InventoryItem.is_active))).all()
    by_slot: dict[int, list[dict]] = defaultdict(list)
    for item in items:
        if item.slot_id is not None and item.quantity > 0:
            by_slot[item.slot_id].append({"id": item.id, "code": item.stock_code, "name": item.name, "quantity": item.quantity})
    companies = (await db.scalars(select(CommercialCompanyProfile).where(CommercialCompanyProfile.is_active))).all()
    return {
        "companies": [{"code": c.company_code, "name": c.trade_name or c.legal_name} for c in companies],
        "areas": [_model(a) for a in areas], "types": [_model(t) for t in types],
        "categories": [_model(c) for c in categories], "subtypes": [_model(s) for s in subtypes],
        "formats": [_model(f) for f in formats],
        "containers": [_model(c) for c in containers],
        "slots": [{**_model(s), "items": by_slot.get(s.id, []), "occupied": bool(by_slot.get(s.id))} for s in slots],
        "unlocated": sum(1 for item in items if item.slot_id is None and item.quantity > 0),
    }


@router.post("/types", status_code=201)
async def create_type(payload: TypeInput, db: AsyncSession = DB, user: User = Depends(require_module("estoque"))):
    item = InventoryLocationType(code=payload.code.lower(), name=payload.name)
    db.add(item)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(409, "Tipo de local já cadastrado.") from None
    await db.refresh(item)
    return _model(item)


@router.put("/types/{type_id}")
async def edit_type(type_id: int, payload: TypeInput, active: bool = True, db: AsyncSession = DB, user: User = Depends(require_module("estoque"))):
    item = await db.get(InventoryLocationType, type_id)
    if item is None:
        raise HTTPException(404, "Tipo não encontrado.")
    item.code, item.name, item.is_active = payload.code.lower(), payload.name, active
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(409, "Código de tipo já utilizado.") from None
    return _model(item)


@router.post("/categories", status_code=201)
async def create_category(payload: CategoryInput, db: AsyncSession = DB, user: User = Depends(require_module("estoque"))):
    category = InventoryComponentCategory(code=payload.code.strip().lower(), name=payload.name.strip())
    db.add(category)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(409, "Tipo de componente já cadastrado.") from None
    await db.refresh(category)
    return _model(category)


@router.put("/categories/{category_id}")
async def edit_category(category_id: int, payload: CategoryInput, db: AsyncSession = DB, user: User = Depends(require_module("estoque"))):
    category = await db.get(InventoryComponentCategory, category_id)
    if not category:
        raise HTTPException(404, "Tipo de componente não encontrado.")
    if payload.code.strip().lower() != category.code:
        raise HTTPException(422, "O código é permanente para preservar cadastros e compras. Edite apenas o nome.")
    category.name = payload.name.strip()
    await db.commit()
    return _model(category)


@router.post("/subtypes", status_code=201)
async def create_subtype(payload: SubtypeInput, db: AsyncSession = DB, user: User = Depends(require_module("estoque"))):
    await _valid_category(db, payload.category)
    subtype = InventoryComponentSubtype(category=payload.category.strip().lower(), code=payload.code.lower(), name=payload.name.strip())
    db.add(subtype)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(409, "Subtipo já cadastrado nesse componente.") from None
    await db.refresh(subtype)
    return _model(subtype)


@router.put("/subtypes/{subtype_id}")
async def edit_subtype(subtype_id: int, payload: SubtypeInput, db: AsyncSession = DB, user: User = Depends(require_module("estoque"))):
    subtype = await db.get(InventoryComponentSubtype, subtype_id)
    if subtype is None:
        raise HTTPException(404, "Subtipo não encontrado.")
    if subtype.category != payload.category.strip().lower() or subtype.code != payload.code.strip().lower():
        raise HTTPException(422, "Categoria e código não podem ser alterados depois do cadastro.")
    subtype.name = payload.name.strip()
    await db.commit()
    return _model(subtype)


async def _valid_category(db: AsyncSession, category: str) -> None:
    code = category.strip().lower()
    result = await db.scalar(select(InventoryComponentCategory.id).where(
        InventoryComponentCategory.code == code, InventoryComponentCategory.is_active.is_(True),
    ))
    if result is None:
        raise HTTPException(422, "Tipo de componente inexistente. Cadastre-o nas configurações do Estoque.")


async def _valid_subtype(db: AsyncSession, subtype_id: int | None, category: str) -> None:
    if subtype_id is None:
        return
    subtype = await db.get(InventoryComponentSubtype, subtype_id)
    if subtype is None or not subtype.is_active or subtype.category != category.strip().lower():
        raise HTTPException(422, "Subtipo incompatível ou inativo para o componente.")


@router.post("/formats", status_code=201)
async def create_format(payload: FormatInput, db: AsyncSession = DB, user: User = Depends(require_module("estoque"))):
    await _valid_category(db, payload.category)
    row = InventoryComponentFormat(category=payload.category.strip().lower(), code=payload.code.lower(), name=payload.name.strip())
    db.add(row)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(409, "Formato já cadastrado nessa categoria.") from None
    await db.refresh(row)
    return _model(row)


@router.put("/formats/{format_id}")
async def edit_format(format_id: int, payload: FormatInput, active: bool = True, db: AsyncSession = DB, user: User = Depends(require_module("estoque"))):
    row = await db.get(InventoryComponentFormat, format_id)
    if row is None:
        raise HTTPException(404, "Formato não encontrado.")
    if row.category != payload.category.strip().lower() or row.code != payload.code.strip().lower():
        raise HTTPException(422, "Categoria e código de formato não podem ser alterados; edite apenas o nome.")
    row.name, row.is_active = payload.name.strip(), active
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(409, "Já existe um formato com esse código nessa categoria.") from None
    return _model(row)


async def _valid_format(db: AsyncSession, format_id: int | None, category: str) -> None:
    if format_id is None:
        return
    row = await db.get(InventoryComponentFormat, format_id)
    if row is None or not row.is_active or row.category != category.strip().lower():
        raise HTTPException(422, "Formato não pertence à categoria informada ou está inativo.")


@router.post("/areas", status_code=201)
async def create_area(payload: AreaInput, db: AsyncSession = DB, user: User = Depends(require_module("estoque"))):
    area = InventoryArea(code=payload.code.upper(), name=payload.name)
    db.add(area)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(409, "Código de área já utilizado.") from None
    await db.refresh(area)
    return _model(area)


@router.put("/areas/{area_id}")
async def edit_area(area_id: int, payload: AreaInput, active: bool = True, db: AsyncSession = DB, user: User = Depends(require_module("estoque"))):
    area = await db.get(InventoryArea, area_id)
    if area is None:
        raise HTTPException(404, "Área não encontrada.")
    area.code, area.name, area.is_active = payload.code.upper(), payload.name, active
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(409, "Código de área já utilizado.") from None
    return _model(area)


@router.delete("/areas/{area_id}", status_code=204)
async def delete_area(area_id: int, db: AsyncSession = DB, user: User = Depends(require_module("estoque"))):
    area = await db.get(InventoryArea, area_id)
    if area is None:
        raise HTTPException(404, "Área não encontrada.")
    if await db.scalar(select(InventoryContainer.id).where(InventoryContainer.area_id == area_id).limit(1)):
        raise HTTPException(409, "Área possui locais cadastrados. Remova primeiro os locais vazios ou mantenha a área inativa.")
    await db.delete(area)
    await db.commit()
    return Response(status_code=204)


@router.delete("/types/{type_id}", status_code=204)
async def delete_location_type(type_id: int, db: AsyncSession = DB, user: User = Depends(require_module("estoque"))):
    kind = await db.get(InventoryLocationType, type_id)
    if kind is None:
        raise HTTPException(404, "Tipo de local não encontrado.")
    if kind.code in {"estante", "gaveta", "caixa", "galeria"}:
        raise HTTPException(409, "Tipo padrão do mapa físico: não pode ser excluído. Remova apenas tipos adicionais.")
    if await db.scalar(select(InventoryContainer.id).where(InventoryContainer.type_id == type_id).limit(1)):
        raise HTTPException(409, "Tipo utilizado em endereços. Remova os endereços antes de excluir o tipo.")
    await db.delete(kind)
    await db.commit()
    return Response(status_code=204)


@router.delete("/containers/{container_id}")
async def delete_container(container_id: int, db: AsyncSession = DB, user: User = Depends(require_module("estoque"))):
    """Remove o endereço e suas posições de fato, mesmo com histórico.

    Antes de excluir um slot, transforma os vínculos históricos em códigos
    textuais de origem/destino. Assim os eventos de localização permanecem
    consultáveis, mas nenhuma FK aponta para as posições que serão apagadas.
    A operação é atômica; em falhas de FK, não arquiva silenciosamente.
    """
    container = await db.get(InventoryContainer, container_id)
    if container is None:
        raise HTTPException(404, "Endereço não encontrado.")
    if await db.scalar(select(InventoryContainer.id).where(
        InventoryContainer.parent_id == container_id
    ).limit(1)):
        raise HTTPException(409, "Este endereço possui sublocais. Exclua os sublocais primeiro.")

    slots = list((await db.scalars(select(InventorySlot).where(
        InventorySlot.container_id == container_id
    ))).all())
    slot_codes = {slot.id: slot.code for slot in slots}
    slot_ids = list(slot_codes)
    if slot_ids:
        if await db.scalar(select(InventoryItem.id).where(
            InventoryItem.slot_id.in_(slot_ids)
        ).limit(1)):
            raise HTTPException(409, "Existem itens neste endereço, mesmo que estejam sem saldo. Transfira-os para outro endereço ou para 'Sem localização' antes de excluir definitivamente.")
        history = list((await db.scalars(select(InventoryLocationHistory).where(
            or_(InventoryLocationHistory.previous_slot_id.in_(slot_ids),
                InventoryLocationHistory.new_slot_id.in_(slot_ids))
        ))).all())
        for event in history:
            # Código é o registro histórico da localização, não uma entidade ativa.
            if event.previous_slot_id in slot_codes:
                event.previous_slot_code = event.previous_slot_code or slot_codes[event.previous_slot_id]
                event.previous_slot_id = None
            if event.new_slot_id in slot_codes:
                event.new_slot_code = event.new_slot_code or slot_codes[event.new_slot_id]
                event.new_slot_id = None

    try:
        # Necessário antes de DELETE por causa das FKs RESTRICT do PostgreSQL.
        await db.flush()
        for slot in slots:
            await db.delete(slot)
        # Forçar a exclusão das posições antes do container (FK RESTRICT).
        await db.flush()
        await db.delete(container)
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(409, "Não foi possível excluir definitivamente: há outro vínculo com o endereço. Atualize a lista e confira os itens e sublocais antes de tentar novamente. Nenhuma alteração foi aplicada.") from None
    return {"outcome": "deleted", "id": container_id,
            "message": "Endereço excluído definitivamente. Os eventos históricos continuam disponíveis."}


@router.post("/containers", status_code=201)
async def create_container(payload: ContainerInput, db: AsyncSession = DB, user: User = Depends(require_module("estoque"))):
    area = await db.get(InventoryArea, payload.area_id)
    kind = await db.get(InventoryLocationType, payload.type_id)
    if not area or not area.is_active or not kind or not kind.is_active:
        raise HTTPException(422, "Área ou tipo inválido.")
    if payload.parent_id:
        parent = await db.get(InventoryContainer, payload.parent_id)
        if parent is None or parent.area_id != payload.area_id or not parent.is_active:
            raise HTTPException(422, "Local superior inválido para esta área.")
    if kind.code == "estante":
        if not (payload.rows == 1 and payload.columns == 5):
            raise HTTPException(422, "Estantes possuem exatamente 1 × 5 posições (A1 a A5).")
        if not (payload.code.isalpha() and payload.code.isascii() and 1 <= len(payload.code) <= 3):
            raise HTTPException(422, "Identifique a estante por letra: A, B, C ... AA.")
    code = payload.code.upper()
    if kind.code == "gaveta":
        import re
        match = re.fullmatch(r"GAVETA-([0-9]+)", code)
        if match is None or int(match.group(1)) < 1:
            raise HTTPException(422, "Use um número de gaveta válido: GAVETA-1, GAVETA-2, etc.")
        number = int(match.group(1))
        current = (await db.scalars(select(InventoryContainer.code))).all()
        if not missing_drawer_numbers(current, start=number, end=number):
            raise HTTPException(409, f"Gaveta {number} já cadastrada. Utilize o endereço existente.")
        code = f"GAVETA-{number}"
    box = InventoryContainer(**payload.model_dump(exclude={"code"}), code=code)
    db.add(box)
    try:
        await db.flush()
        for row in range(1, box.rows + 1):
            for column in range(1, box.columns + 1):
                if kind.code == "estante":
                    code = f"{box.code}{column}"
                    name = f"Estante {box.code} - posição {column}"
                elif box.rows * box.columns == 1:
                    code = box.code
                    name = box.name
                else:
                    code = f"{box.code}-{row:02d}-{column:02d}"
                    name = f"Posição {row}.{column}"
                db.add(InventorySlot(container_id=box.id, code=code, name=name, row=row, column=column))
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(409, "Código de localização já utilizado.") from None
    return {"id": box.id, "code": box.code, "positions": box.rows * box.columns}


@router.post("/containers/batch-drawers")
async def ensure_drawers_1_to_493(area_id: int, db: AsyncSession = DB, user: User = Depends(require_module("estoque"))):
    """Cria de forma idempotente gavetas 1..493 na área indicada, preservando as existentes.

    Repetir a operação não duplica endereços; tudo é confirmado numa única transação.
    """
    area = await db.get(InventoryArea, area_id)
    if area is None or not area.is_active:
        raise HTTPException(422, "Selecione uma área ativa para cadastrar as gavetas.")
    drawer_type = await db.scalar(select(InventoryLocationType).where(InventoryLocationType.code == "gaveta", InventoryLocationType.is_active.is_(True)))
    if drawer_type is None:
        raise HTTPException(422, "Tipo de local Gaveta não está cadastrado ou ativo.")
    existing = (await db.scalars(select(InventoryContainer.code))).all()
    missing = missing_drawer_numbers(existing, start=1, end=493)
    if not missing:
        return {"created": 0, "already_registered": 493, "total": 493}
    try:
        for number in missing:
            code = f"GAVETA-{number}"
            drawer = InventoryContainer(
                area_id=area.id, type_id=drawer_type.id, parent_id=None,
                code=code, name=f"Gaveta {number}", rows=1, columns=1,
                layout_row=1, layout_column=1, layout_span=1,
            )
            db.add(drawer)
            await db.flush()
            db.add(InventorySlot(container_id=drawer.id, code=code, name=drawer.name, row=1, column=1))
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(409, "Uma gaveta foi cadastrada simultaneamente. Atualize os endereços e tente novamente.") from None
    return {"created": len(missing), "already_registered": 493 - len(missing), "total": 493}


@router.put("/containers/{container_id}")
async def edit_container(container_id: int, payload: ContainerUpdate, db: AsyncSession = DB, user: User = Depends(require_module("estoque"))):
    item = await db.get(InventoryContainer, container_id)
    if item is None:
        raise HTTPException(404, "Local não encontrado.")
    slots = list((await db.scalars(select(InventorySlot).where(InventorySlot.container_id == container_id))).all())
    if not payload.is_active and item.is_active:
        if await db.scalar(select(InventoryContainer.id).where(InventoryContainer.parent_id == container_id).limit(1)):
            raise HTTPException(409, "Remova os sublocais antes de arquivar este endereço.")
        if slots and await db.scalar(select(InventoryItem.id).where(InventoryItem.slot_id.in_([s.id for s in slots])).limit(1)):
            raise HTTPException(409, "Realoque os itens associados antes de inativar este endereço.")
    status_changed = item.is_active != payload.is_active
    for k, v in payload.model_dump().items():
        setattr(item, k, v)
    # Só mudar o estado das posições quando o próprio endereço mudar de estado.
    # Renomear um endereço ativo não deve reativar posições antes inativadas.
    if status_changed:
        for slot in slots:
            slot.is_active = payload.is_active
    await db.commit()
    return _model(item)


@router.get("/items")
async def list_items(search: str = Query(default="", max_length=120), company_code: str | None = None, db: AsyncSession = DB, user: User = USER):
    statement = select(InventoryItem).order_by(InventoryItem.id.desc()).limit(500)
    if search:
        term = f"%{search.strip()}%"
        matched_id = stock_id_from_query(search)
        clauses = [InventoryItem.name.ilike(term), InventoryItem.stock_code.ilike(term), InventoryItem.manufacturer_serial.ilike(term), InventoryItem.category.ilike(term), InventoryItem.format_id.in_(select(InventoryComponentFormat.id).where(InventoryComponentFormat.name.ilike(term)))]
        if matched_id is not None:
            clauses.append(InventoryItem.id == matched_id)
        statement = statement.where(or_(*clauses))
    if company_code:
        statement = statement.where(InventoryItem.company_code == company_code)
    rows = (await db.scalars(statement)).all()
    slots = {s.id: s.code for s in (await db.scalars(select(InventorySlot))).all()}
    photos = (await db.scalars(select(InventoryPhoto).where(InventoryPhoto.item_id.in_([i.id for i in rows])))).all() if rows else []
    photo_ids: dict[int, list[int]] = defaultdict(list)
    for p in photos:
        photo_ids[p.item_id].append(p.id)
    return [_item_dict(i, user, slots.get(i.slot_id), photo_ids.get(i.id)) for i in rows]


@router.post("/items", status_code=201)
async def create_item(payload: ItemInput, db: AsyncSession = DB, user: User = Depends(require_module("estoque"))):
    await _valid_slot(db, payload.slot_id)
    await _valid_category(db, payload.category)
    await _valid_subtype(db, payload.subtype_id, payload.category)
    await _valid_format(db, payload.format_id, payload.category)
    active_company = await db.scalar(select(CommercialCompanyProfile.id).where(
        CommercialCompanyProfile.company_code == payload.company_code,
        CommercialCompanyProfile.is_active.is_(True),
    ))
    if active_company is None:
        raise HTTPException(422, "Empresa do estoque inválida ou inativa.")
    if payload.unit_cost and not _money_allowed(user):
        raise HTTPException(403, "Somente Gestão pode definir custos de peças.")
    normalized = payload.manufacturer_serial.strip().upper() if payload.mode == "serialized" and payload.manufacturer_serial else None
    item = InventoryItem(
        **payload.model_dump(exclude={"manufacturer_serial", "unit_cost"}),
        stock_code=f"TMP-{uuid4().hex[:24]}",
        manufacturer_serial=payload.manufacturer_serial.strip() if payload.manufacturer_serial else None,
        serial_normalized=normalized, unit_cost=payload.unit_cost, created_by=user.id,
    )
    db.add(item)
    try:
        await db.flush()
        item.stock_code = format_stock_code(item.id)
        if item.slot_id is not None:
            slot = await db.get(InventorySlot, item.slot_id)
            db.add(InventoryLocationHistory(item_id=item.id, new_slot_id=item.slot_id,
                new_slot_code=slot.code if slot else None, moved_by=user.id))
        db.add(InventoryMovement(item_id=item.id, kind="receipt", quantity=item.quantity, unit_cost=item.unit_cost, user_id=user.id, note="Cadastro inicial")) if item.quantity else None
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(409, "Número de série já cadastrado nesta empresa.") from None
    await db.refresh(item)
    return _item_dict(item, user)


@router.put("/items/{item_id}")
async def edit_item(item_id: int, payload: ItemUpdate, db: AsyncSession = DB, user: User = Depends(require_module("estoque"))):
    item = await db.get(InventoryItem, item_id)
    if item is None:
        raise HTTPException(404, "Item não encontrado.")
    await _valid_slot(db, payload.slot_id)
    await _valid_category(db, payload.category)
    await _valid_subtype(db, payload.subtype_id, payload.category)
    await _valid_format(db, payload.format_id, payload.category)
    # O contrato ItemUpdate não permite alterar a empresa de um item que já
    # possui série, saldo ou movimentações vinculadas a uma OS. A empresa é fixa.
    if payload.unit_cost is not None and not _money_allowed(user):
        raise HTTPException(403, "Somente Gestão pode editar custo de peças.")
    old_slot = item.slot_id
    # Clientes V5 não enviam subtype_id: preservar o subtipo salvo ao editar
    # outros campos, exceto quando a categoria técnica é modificada.
    changing_category = payload.category.strip().lower() != item.category.strip().lower()
    for key, value in payload.model_dump(exclude={"unit_cost"}).items():
        if key == "subtype_id" and key not in payload.model_fields_set:
            if changing_category:
                item.subtype_id = None
            continue
        setattr(item, key, value)
    if old_slot != item.slot_id:
        previous_slot = await db.get(InventorySlot, old_slot) if old_slot else None
        new_slot = await db.get(InventorySlot, item.slot_id) if item.slot_id else None
        db.add(InventoryLocationHistory(
            item_id=item.id, previous_slot_id=old_slot, new_slot_id=item.slot_id,
            previous_slot_code=previous_slot.code if previous_slot else None,
            new_slot_code=new_slot.code if new_slot else None,
            moved_by=user.id,
        ))
    if payload.unit_cost is not None:
        item.unit_cost = payload.unit_cost
    await db.commit()
    return _item_dict(item, user)


async def _change(item_id: int, payload: MovementInput, kind: str, db: AsyncSession, user: User):
    if kind == "issue" and payload.work_order_id is None:
        raise HTTPException(422, "Informe a ordem de serviço para baixar a peça.")
    if kind == "issue" and payload.reversal_of_id is not None:
        raise HTTPException(422, "Saída não pode referenciar devolução.")
    if kind == "return" and (payload.work_order_id is None or payload.reversal_of_id is None):
        raise HTTPException(422, "Informe a O.S. e a saída original da devolução.")
    if kind == "receipt" and (payload.work_order_id is not None or payload.reversal_of_id is not None):
        raise HTTPException(422, "Recebimento não utiliza O.S. nem devolução.")
    movement = await move_stock(db, item_id=item_id, quantity=payload.quantity, kind=kind,
        user_id=user.id, work_order_id=payload.work_order_id, reversal_of_id=payload.reversal_of_id, note=payload.note)
    await db.commit()
    return {"id": movement.id, "kind": movement.kind, "quantity": movement.quantity, "item_id": item_id}


@router.post("/items/{item_id}/receive")
async def receive_item(item_id: int, payload: MovementInput, db: AsyncSession = DB, user: User = Depends(require_module("estoque"))):
    item = await db.get(InventoryItem, item_id)
    if item is None:
        raise HTTPException(404, "Item não encontrado.")
    if item.mode == "serialized":
        raise HTTPException(409, "Equipamento individual não admite novas entradas; cadastre outra série.")
    return await _change(item_id, payload, "receipt", db, user)


@router.post("/items/{item_id}/issue")
async def issue_item(item_id: int, payload: MovementInput, db: AsyncSession = DB, user: User = USER):
    return await _change(item_id, payload, "issue", db, user)


@router.post("/items/{item_id}/return")
async def return_item(item_id: int, payload: MovementInput, db: AsyncSession = DB, user: User = USER):
    return await _change(item_id, payload, "return", db, user)


@router.get("/work-orders/{work_order_id}/movements")
async def work_order_movements(work_order_id: int, db: AsyncSession = DB, user: User = USER):
    rows = (await db.scalars(select(InventoryMovement).where(
        InventoryMovement.work_order_id == work_order_id
    ).order_by(InventoryMovement.created_at.desc(), InventoryMovement.id.desc()))).all()
    ids = {m.item_id for m in rows}
    items = {i.id: i for i in (await db.scalars(select(InventoryItem).where(InventoryItem.id.in_(ids)))).all()} if ids else {}
    result = []
    for m in rows:
        data = _model(m)
        if not _money_allowed(user):
            data.pop("unit_cost", None)
        part = items.get(m.item_id)
        data.update(stock_code=part.stock_code if part else "", item_name=part.name if part else "", manufacturer_serial=part.manufacturer_serial if part else None)
        result.append(data)
    return result


@router.get("/items/{item_id}/location-history")
async def location_history(item_id: int, db: AsyncSession = DB):
    rows = (await db.scalars(select(InventoryLocationHistory).where(
        InventoryLocationHistory.item_id == item_id
    ).order_by(InventoryLocationHistory.id.desc()))).all()
    slots = {s.id: s.code for s in (await db.scalars(select(InventorySlot))).all()}
    return [{
        "id": row.id, "from": row.previous_slot_code or slots.get(row.previous_slot_id),
        "to": row.new_slot_code or slots.get(row.new_slot_id), "created_at": row.created_at,
        "moved_by": row.moved_by,
    } for row in rows]


@router.get("/items/{item_id}/movements")
async def item_movements(item_id: int, db: AsyncSession = DB, user: User = USER):
    rows = (await db.scalars(select(InventoryMovement).where(InventoryMovement.item_id == item_id).order_by(InventoryMovement.id.desc()))).all()
    result = []
    for item in rows:
        data = _model(item)
        if not _money_allowed(user):
            data.pop("unit_cost", None)
        result.append(data)
    return result


@router.post("/items/{item_id}/photos", status_code=201)
async def upload_photo(item_id: int, file: UploadFile = File(...), db: AsyncSession = DB, user: User = Depends(require_module("estoque"))):
    item = await db.get(InventoryItem, item_id)
    if item is None:
        raise HTTPException(404, "Item não encontrado.")
    try:
        upload = await persist_streamed_upload(file, directory=STORAGE / str(item_id), max_size=10 * 1024 * 1024)
    except (InvalidUpload, UploadTooLarge) as error:
        raise HTTPException(422, str(error)) from error
    if upload.mime_type not in {"image/jpeg", "image/png", "image/webp"}:
        upload.path.unlink(missing_ok=True)
        raise HTTPException(422, "Somente fotos JPG, PNG ou WEBP.")
    photo = InventoryPhoto(item_id=item_id, filename=upload.path.name, mime_type=upload.mime_type, created_by=user.id)
    db.add(photo)
    try:
        await db.commit()
    except Exception:
        upload.path.unlink(missing_ok=True)
        raise
    await db.refresh(photo)
    return {"id": photo.id, "item_id": item_id}


@router.get("/photos/{photo_id}")
async def show_photo(photo_id: int, db: AsyncSession = DB):
    photo = await db.get(InventoryPhoto, photo_id)
    if photo is None:
        raise HTTPException(404, "Foto não encontrada.")
    path = STORAGE / str(photo.item_id) / Path(photo.filename).name
    if not path.is_file():
        raise HTTPException(404, "Arquivo da foto indisponível.")
    return FileResponse(path, media_type=photo.mime_type)


@router.get("/items/{item_id}/label.pdf")
async def label(item_id: int, db: AsyncSession = DB):
    item = await db.get(InventoryItem, item_id)
    if item is None:
        raise HTTPException(404, "Item não encontrado.")
    slot = await db.get(InventorySlot, item.slot_id) if item.slot_id else None
    content = await asyncio.to_thread(
        inventory_label_pdf, stock_code=item.stock_code, name=item.name,
        serial=item.manufacturer_serial, location=_readable_location(slot.code) if slot else "SEM LOCAL",
    )
    return Response(content=content, media_type="application/pdf", headers={"Content-Disposition": f'inline; filename="{item.stock_code}.pdf"'})
