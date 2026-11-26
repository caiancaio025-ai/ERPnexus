from fastapi import APIRouter, HTTPException, Response, status
from pydantic import BaseModel

from app.core.db import database_is_ready

router = APIRouter()


@router.get("/version")
def version(response: Response) -> dict[str, str]:
    response.headers["Cache-Control"] = "no-store"
    return {"version": "48", "release_date": "2026-11-26", "name": "SENTICO",
            "revision": "v48-20261126-faturamento-estoque", "schema_revision": "20261126_04"}


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
