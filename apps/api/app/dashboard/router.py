from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.models import User
from app.auth.router import current_user
from app.core.db import get_db
from app.dashboard.schemas import DashboardSummary
from app.dashboard.service import build_summary

router = APIRouter(prefix="/dashboard")


@router.get("/summary", response_model=DashboardSummary)
async def summary(
    response: Response,
    user: User = Depends(current_user),
    db: AsyncSession = Depends(get_db),
) -> DashboardSummary:
    response.headers["Cache-Control"] = "no-store"
    return await build_summary(user, db)
