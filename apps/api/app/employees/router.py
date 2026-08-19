from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_any_module
from app.auth.models import User
from app.auth.router import current_user
from app.core.db import get_db
from app.employees.models import Employee
from app.employees.schemas import (
    EmployeeCreate,
    EmployeeDetailResponse,
    EmployeeListResponse,
    EmployeeTerminateRequest,
    EmployeeUpdate,
    PaginatedEmployeeResponse,
)
from app.employees.service import EmployeeService

router = APIRouter(
    prefix="/employees",
    dependencies=[Depends(require_any_module("colaboradores", "configuracoes"))],
)

DbSession = Annotated[AsyncSession, Depends(get_db)]
CurrentUser = Annotated[User, Depends(current_user)]


@router.get("", response_model=PaginatedEmployeeResponse)
async def list_employees(
    db: DbSession,
    _: CurrentUser,
    company_code: str = Query("universo_eletronica"),
    department: str | None = Query(None),
    is_active: bool | None = Query(None),
    limit: int = Query(25, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    employees, total = await EmployeeService.get_employees(
        db, company_code, department, is_active, limit, offset
    )
    return PaginatedEmployeeResponse(
        total=total,
        limit=limit,
        offset=offset,
        data=[EmployeeListResponse.model_validate(item) for item in employees],
    )


@router.post("", response_model=EmployeeDetailResponse, status_code=status.HTTP_201_CREATED)
async def create_employee(payload: EmployeeCreate, db: DbSession, user: CurrentUser):
    exists = await db.scalar(
        select(Employee.id).where(
            Employee.company_code == payload.company_code,
            Employee.document == payload.document,
        )
    )
    if exists:
        raise HTTPException(status_code=409, detail="Já existe colaborador com este CPF/CNPJ para a empresa.")
    employee = await EmployeeService.create_employee(db, payload, user.id)
    return EmployeeDetailResponse.model_validate(employee)


@router.get("/{employee_id}", response_model=EmployeeDetailResponse)
async def get_employee(employee_id: int, db: DbSession, _: CurrentUser):
    employee = await EmployeeService.get_employee(db, employee_id)
    if not employee:
        raise HTTPException(status_code=404, detail="Colaborador não encontrado.")
    return EmployeeDetailResponse.model_validate(employee)


@router.put("/{employee_id}", response_model=EmployeeDetailResponse)
async def update_employee(employee_id: int, payload: EmployeeUpdate, db: DbSession, user: CurrentUser):
    employee = await EmployeeService.update_employee(db, employee_id, payload, user.id)
    if not employee:
        raise HTTPException(status_code=404, detail="Colaborador não encontrado.")
    return EmployeeDetailResponse.model_validate(employee)


@router.post("/{employee_id}/terminate", response_model=EmployeeDetailResponse)
async def terminate_employee(employee_id: int, payload: EmployeeTerminateRequest, db: DbSession, user: CurrentUser):
    employee = await EmployeeService.terminate_employee(db, employee_id, payload, user.id)
    if not employee:
        raise HTTPException(status_code=404, detail="Colaborador não encontrado.")
    return EmployeeDetailResponse.model_validate(employee)


@router.post("/{employee_id}/reactivate", response_model=EmployeeDetailResponse)
async def reactivate_employee(employee_id: int, db: DbSession, user: CurrentUser):
    employee = await EmployeeService.reactivate_employee(db, employee_id, user.id)
    if not employee:
        raise HTTPException(status_code=404, detail="Colaborador não encontrado.")
    return EmployeeDetailResponse.model_validate(employee)
