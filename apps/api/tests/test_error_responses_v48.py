from types import SimpleNamespace

import httpx
import pytest
from fastapi import FastAPI
from sqlalchemy.exc import DataError, IntegrityError, OperationalError, TimeoutError

from app.core.errors import register_error_handlers
from app.core.observability import request_observability_middleware
from app.main import app as real_app


@pytest.mark.parametrize("failure,expected", [
    (IntegrityError("secret SQL", {"password": "secret"}, SimpleNamespace(sqlstate="23505")), 409),
    (IntegrityError("secret SQL", {}, SimpleNamespace(sqlstate="23503")), 409),
    (DataError("secret SQL", {}, Exception("secret")), 422),
    (OperationalError("secret SQL", {}, Exception("secret")), 503),
    (TimeoutError("secret"), 503),
    (RuntimeError("secret"), 500),
])
async def test_server_failures_have_safe_json_and_diagnostic_id(failure, expected):
    app = FastAPI()
    app.middleware("http")(request_observability_middleware)
    register_error_handlers(app)

    @app.post("/save")
    async def failing_save():
        raise failure

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app, raise_app_exceptions=False), base_url="http://testserver") as client:
        response = await client.post("/save", headers={"X-Request-ID": "v48-error-test-0001"})
    assert response.status_code == expected
    assert response.headers["X-Request-ID"] == "v48-error-test-0001"
    assert response.json()["request_id"] == "v48-error-test-0001"
    assert response.json()["detail"]
    assert "secret" not in response.text


async def test_finance_idempotency_header_is_allowed_by_cors():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=real_app), base_url="http://testserver") as client:
        response = await client.options("/finance/entries", headers={
            "Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type,idempotency-key,x-request-id",
        })
    assert response.status_code == 200
    assert "idempotency-key" in response.headers["access-control-allow-headers"].lower()
