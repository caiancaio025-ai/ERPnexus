from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.core.db import database_is_ready

router = APIRouter()


class Health(BaseModel):
    status: str


@router.get("/live", response_model=Health)
def live() -> Health:
    return Health(status="ok")


@router.get("/ready", response_model=Health)
async def ready() -> Health:
    if not await database_is_ready():
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE)
    return Health(status="ok")
