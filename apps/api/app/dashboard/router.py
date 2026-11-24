from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.auth.router import current_user
from app.core.db import get_db
from app.dashboard.schemas import DashboardSummary
from app.dashboard.service import build_summary, resolve_dashboard_period

router = APIRouter(prefix="/dashboard")


@router.get("/summary", response_model=DashboardSummary)
async def summary(
    response: Response,
    periodo: str = Query("todos"),
    inicio: date | None = Query(None),
    fim: date | None = Query(None),
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> DashboardSummary:
    response.headers["Cache-Control"] = "no-store"
    try:
        filtro = resolve_dashboard_period(periodo, inicio, fim)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return await build_summary(user, db, filtro)
