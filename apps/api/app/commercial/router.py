from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_module
from app.auth.models import User
from app.auth.router import current_user
from app.commercial.label_pdf import commercial_label_pdf
from app.commercial.models import CommercialEquipment
from app.commercial.schemas import CommercialEquipmentInput, CommercialEquipmentOutput
from app.core.db import get_db

router = APIRouter(prefix="/commercial", dependencies=[Depends(require_module("comercial"))])
DbSession = Annotated[AsyncSession, Depends(get_db)]
CurrentUser = Annotated[User, Depends(current_user)]


async def _equipment_or_404(db: AsyncSession, equipment_id: int) -> CommercialEquipment:
    equipment = await db.get(CommercialEquipment, equipment_id)
    if not equipment or not equipment.is_active:
        raise HTTPException(status_code=404, detail="Equipamento comercial não encontrado.")
    return equipment


@router.get("/equipment", response_model=list[CommercialEquipmentOutput])
async def list_equipment(
    _: CurrentUser,
    db: DbSession,
    search: Annotated[str | None, Query(max_length=120)] = None,
):
    query = select(CommercialEquipment).where(CommercialEquipment.is_active.is_(True))
    if search:
        term = f"%{search.strip()}%"
        query = query.where(
            or_(
                CommercialEquipment.serial_code.ilike(term),
                CommercialEquipment.equipment_type.ilike(term),
                CommercialEquipment.manufacturer.ilike(term),
                CommercialEquipment.model.ilike(term),
            )
        )
    query = query.order_by(CommercialEquipment.id.desc())
    return list((await db.scalars(query)).all())


@router.post("/equipment", response_model=CommercialEquipmentOutput, status_code=status.HTTP_201_CREATED)
async def create_equipment(payload: CommercialEquipmentInput, user: CurrentUser, db: DbSession):
    equipment = CommercialEquipment(**payload.model_dump(), created_by=user.id)
    db.add(equipment)
    await db.flush()
    equipment.serial_code = f"{equipment.id:03d}"
    await db.commit()
    await db.refresh(equipment)
    return equipment


@router.put("/equipment/{equipment_id}", response_model=CommercialEquipmentOutput)
async def update_equipment(
    equipment_id: int,
    payload: CommercialEquipmentInput,
    _: CurrentUser,
    db: DbSession,
):
    equipment = await _equipment_or_404(db, equipment_id)
    for key, value in payload.model_dump().items():
        setattr(equipment, key, value)
    await db.commit()
    await db.refresh(equipment)
    return equipment


@router.delete("/equipment/{equipment_id}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_equipment(equipment_id: int, _: CurrentUser, db: DbSession):
    equipment = await _equipment_or_404(db, equipment_id)
    equipment.is_active = False
    await db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/equipment/{equipment_id}/label.pdf")
async def equipment_label(equipment_id: int, _: CurrentUser, db: DbSession):
    equipment = await _equipment_or_404(db, equipment_id)
    pdf = commercial_label_pdf(equipment)
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="etiqueta-comercial-{equipment.serial_code}.pdf"'},
    )
