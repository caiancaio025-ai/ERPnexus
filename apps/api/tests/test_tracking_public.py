# cspell:ignore substatuses

import asyncio
from collections.abc import Callable
from datetime import date
from types import SimpleNamespace
from typing import cast

from fastapi.responses import HTMLResponse
from pytest import MonkeyPatch
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request

import app.tracking.router as tracking_router
from app.tracking.rate_limit import TrackingRateLimitState

PageFactory = Callable[[str, str], HTMLResponse]


def _request() -> Request:
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/e/token",
            "headers": [],
            "client": ("127.0.0.1", 12345),
            "server": ("testserver", 80),
            "scheme": "http",
            "query_string": b"",
        }
    )


def _response_text(response: HTMLResponse) -> str:
    body: object = response.body
    if isinstance(body, str):
        return body
    if isinstance(body, memoryview):
        return body.tobytes().decode("utf-8")
    if isinstance(body, (bytes, bytearray)):
        return bytes(body).decode("utf-8")
    raise TypeError(f"Unsupported response body type: {type(body)!r}")


async def _allow_tracking(_db: object, _request: Request) -> TrackingRateLimitState:
    return TrackingRateLimitState(blocked=False)


class FakeDb:
    def __init__(self, *results: object) -> None:
        self.results = iter(results)

    async def scalar(self, _query: object) -> object:
        return next(self.results)


def _db(*results: object) -> AsyncSession:
    return cast(AsyncSession, FakeDb(*results))


def test_tracking_page_escapes_untrusted_content() -> None:
    page = cast(PageFactory, getattr(tracking_router, "_page"))
    response = page("OS <script>", '<section class="card">ok</section>')
    body = _response_text(response)

    assert "OS &lt;script&gt; · NEXUS" in body
    assert "<title>OS <script>" not in body
    assert response.headers["cache-control"] == "no-store"


def test_tracking_route_rejects_invalid_token_without_database_lookup(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        tracking_router,
        "tracking_rate_limit_state",
        _allow_tracking,
    )

    response = asyncio.run(
        tracking_router.public_work_order_tracking(
            "short",
            _request(),
            _db(),
        )
    )

    assert response.status_code == 404
    assert "Consulta não encontrada" in _response_text(response)


def test_tracking_route_renders_public_work_order_data(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(
        tracking_router,
        "tracking_rate_limit_state",
        _allow_tracking,
    )

    work_order = SimpleNamespace(
        id=7,
        number="OS-0007",
        customer_name="Cliente Exemplo",
        status="in_repair",
        opened_at=date(2026, 8, 13),
        equipment_serial="SN-123",
        equipment=SimpleNamespace(
            equipment_type="Inversor de frequência",
            manufacturer="WEG",
            model="CFW11",
        ),
        technician=SimpleNamespace(name="Técnico Reserva"),
        substatuses=[
            SimpleNamespace(
                code="quote_sent",
                is_active=True,
            ),
        ],
    )

    response = asyncio.run(
        tracking_router.public_work_order_tracking(
            "0123456789abcdef0123456789abcdef",
            _request(),
            _db(work_order, "Técnico Atual"),
        )
    )

    body = _response_text(response)

    assert response.status_code == 200
    assert "OS-0007" in body
    assert "Cliente Exemplo" not in body
    assert "Em reparo" in body
    assert "Orçamento enviado" in body
    assert "13/08/2026" in body
    assert "SN-123" not in body
    assert "Técnico Atual" not in body
    assert "Cache-Control" not in body


def test_tracking_route_returns_429_when_ip_is_limited(
    monkeypatch: MonkeyPatch,
) -> None:
    async def blocked(
        _db: object,
        _request: Request,
    ) -> TrackingRateLimitState:
        return TrackingRateLimitState(
            blocked=True,
            retry_after=17,
        )

    monkeypatch.setattr(
        tracking_router,
        "tracking_rate_limit_state",
        blocked,
    )

    response = asyncio.run(
        tracking_router.public_work_order_tracking(
            "0123456789abcdef0123456789abcdef",
            _request(),
            _db(),
        )
    )

    assert response.status_code == 429
    assert response.headers["retry-after"] == "17"
    assert response.headers["cache-control"] == "no-store"
