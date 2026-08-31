import logging
import re
from time import perf_counter
from uuid import uuid4

from fastapi import Request, Response


logger = logging.getLogger("uvicorn.error")

_REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{8,128}$")


def get_request_id(value: str | None) -> str:
    if value and _REQUEST_ID_PATTERN.fullmatch(value):
        return value

    return uuid4().hex


async def request_observability_middleware(
    request: Request,
    call_next,
) -> Response:
    request_id = get_request_id(request.headers.get("X-Request-ID"))
    request.state.request_id = request_id

    started_at = perf_counter()

    try:
        response = await call_next(request)
    except Exception:
        duration_ms = (perf_counter() - started_at) * 1000

        logger.exception(
            "request_failed method=%s path=%s duration_ms=%.2f request_id=%s",
            request.method,
            request.url.path,
            duration_ms,
            request_id,
        )
        raise

    duration_ms = (perf_counter() - started_at) * 1000

    response.headers["X-Request-ID"] = request_id

    logger.info(
        "request method=%s path=%s status=%s duration_ms=%.2f request_id=%s",
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
        request_id,
    )

    return response