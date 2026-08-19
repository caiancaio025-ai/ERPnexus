from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.employees.models import Employee, EmployeeAuditEvent, EmploymentHistory
from app.employees.schemas import EmployeeCreate, EmployeeTerminateRequest, EmployeeUpdate


class EmployeeService:
    @staticmethod
    async def create_employee(db: AsyncSession, payload: EmployeeCreate, user_id: int) -> Employee:
        employee = Employee(**payload.model_dump(), created_by=user_id)
        db.add(employee)
        await db.flush()
        db.add(EmployeeAuditEvent(
            employee_id=employee.id,
            action="employee_created",
            description=f"Colaborador {employee.full_name} cadastrado",
            user_id=user_id,
        ))
        await db.commit()
        return await EmployeeService.get_employee(db, employee.id)  # type: ignore[return-value]

    @staticmethod
    async def get_employee(db: AsyncSession, employee_id: int) -> Employee | None:
        return await db.scalar(
            select(Employee)
            .options(selectinload(Employee.employment_history), selectinload(Employee.documents))
            .where(Employee.id == employee_id)
        )

    @staticmethod
    async def get_employees(
        db: AsyncSession,
        company_code: str,
        department: str | None = None,
        is_active: bool | None = None,
        limit: int = 25,
        offset: int = 0,
    ) -> tuple[list[Employee], int]:
        filters = [Employee.company_code == company_code]
        if department:
            filters.append(Employee.department == department)
        if is_active is not None:
            filters.append(Employee.is_active.is_(is_active))

        total = int(await db.scalar(select(func.count()).select_from(Employee).where(*filters)) or 0)
        result = await db.scalars(
            select(Employee).where(*filters).order_by(Employee.full_name).limit(limit).offset(offset)
        )
        return list(result.all()), total

    @staticmethod
    async def update_employee(db: AsyncSession, employee_id: int, payload: EmployeeUpdate, user_id: int) -> Employee | None:
        employee = await EmployeeService.get_employee(db, employee_id)
        if not employee:
            return None
        before = {"department": employee.department, "position": employee.position, "salary_base": str(employee.salary_base), "is_active": employee.is_active}
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(employee, field, value)
        after = {"department": employee.department, "position": employee.position, "salary_base": str(employee.salary_base), "is_active": employee.is_active}
        db.add(EmployeeAuditEvent(
            employee_id=employee.id,
            action="employee_updated",
            description=f"Cadastro de {employee.full_name} atualizado",
            user_id=user_id,
            before_data=before,
            after_data=after,
        ))
        await db.commit()
        return await EmployeeService.get_employee(db, employee.id)

    @staticmethod
    async def terminate_employee(db: AsyncSession, employee_id: int, payload: EmployeeTerminateRequest, user_id: int) -> Employee | None:
        employee = await EmployeeService.get_employee(db, employee_id)
        if not employee:
            return None
        employee.termination_date = payload.termination_date
        employee.is_active = False
        db.add(EmploymentHistory(
            employee_id=employee.id,
            start_date=employee.hiring_date,
            end_date=payload.termination_date,
            department=employee.department,
            position=employee.position,
            salary=employee.salary_base,
            employment_type=employee.employment_type,
            reason_end=payload.reason_end,
        ))
        db.add(EmployeeAuditEvent(
            employee_id=employee.id,
            action="employee_terminated",
            description=f"Colaborador {employee.full_name} desligado: {payload.reason_end}",
            user_id=user_id,
        ))
        await db.commit()
        return await EmployeeService.get_employee(db, employee.id)

    @staticmethod
    async def reactivate_employee(db: AsyncSession, employee_id: int, user_id: int) -> Employee | None:
        employee = await EmployeeService.get_employee(db, employee_id)
        if not employee:
            return None
        employee.termination_date = None
        employee.is_active = True
        db.add(EmployeeAuditEvent(
            employee_id=employee.id,
            action="employee_reactivated",
            description=f"Colaborador {employee.full_name} reativado",
            user_id=user_id,
        ))
        await db.commit()
        return await EmployeeService.get_employee(db, employee.id)
