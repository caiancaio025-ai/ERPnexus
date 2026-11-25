"""Stable error responses without exposing SQL, credentials or request payloads."""

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import DataError, IntegrityError, OperationalError, TimeoutError

from app.core.observability import get_request_id

logger = logging.getLogger("uvicorn.error")


def _error_response(request: Request, code: int, detail: str) -> JSONResponse:
    request_id = getattr(request.state, "request_id", None) or get_request_id(None)
    return JSONResponse(
        status_code=code,
        content={"detail": detail, "request_id": request_id},
        headers={"X-Request-ID": request_id, "Cache-Control": "no-store"},
    )


async def database_error(request: Request, exc: Exception) -> JSONResponse:
    sqlstate = getattr(getattr(exc, "orig", None), "sqlstate", None)
    if isinstance(exc, IntegrityError):
        code = 409
        if sqlstate == "23503":
            detail = "O registro possui um vínculo inválido ou está sendo utilizado em outro cadastro. Atualize os dados e confira os vínculos."
        elif sqlstate == "23505":
            detail = "Já existe um registro com esta identificação. Atualize a consulta antes de cadastrar novamente."
        else:
            detail = "Os dados entram em conflito com outro registro ou com uma regra do cadastro. Atualize a consulta e confira os campos."
    elif isinstance(exc, DataError):
        code = 422
        detail = "Um dos valores está fora do formato ou tamanho permitido. Confira os campos informados."
    else:
        code = 503
        detail = "A comunicação com o banco ficou indisponível. Não foi possível confirmar a operação. Consulte o registro antes de repetir o envio."
    # Do not log exc/statement/params: database exceptions can contain client data.
    logger.error(
        "database_error method=%s path=%s kind=%s sqlstate=%s request_id=%s",
        request.method, request.url.path, type(exc).__name__, sqlstate,
        getattr(request.state, "request_id", None),
    )
    return _error_response(request, code, detail)


async def unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    # The observability middleware logs the server traceback. The browser receives
    # the same diagnostic ID even when Starlette generates an outer 500 response.
    return _error_response(
        request, 500,
        "Não foi possível confirmar a operação. Consulte o registro antes de repetir o envio e informe o código de atendimento se o erro persistir.",
    )


def register_error_handlers(app: FastAPI) -> None:
    for error_type in (IntegrityError, DataError, OperationalError, TimeoutError):
        app.add_exception_handler(error_type, database_error)
    app.add_exception_handler(Exception, unexpected_error)
