import asyncio
from datetime import date
from types import SimpleNamespace

from app.tracking.router import _page, public_work_order_tracking


class FakeDb:
    def __init__(self, *results: object) -> None:
        self.results = iter(results)

    async def scalar(self, _query: object) -> object:
        return next(self.results)


def test_tracking_page_escapes_untrusted_content() -> None:
    response = _page("OS <script>", '<section class="card">ok</section>')
    body = response.body.decode("utf-8")

    assert "OS &lt;script&gt; · NEXUS" in body
    assert "<title>OS <script>" not in body
    assert response.headers["cache-control"] == "no-store"


def test_tracking_route_rejects_invalid_token_without_database_lookup() -> None:
    response = asyncio.run(public_work_order_tracking("short", FakeDb()))

    assert response.status_code == 404
    assert "Consulta não encontrada" in response.body.decode("utf-8")


def test_tracking_route_renders_public_work_order_data() -> None:
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
    )
    db = FakeDb(work_order, "Técnico Atual")

    response = asyncio.run(
        public_work_order_tracking("0123456789abcdef0123456789abcdef", db)
    )
    body = response.body.decode("utf-8")

    assert response.status_code == 200
    assert "OS-0007" in body
    assert "Cliente Exemplo" in body
    assert "Em reparo" in body
    assert "13/08/2026" in body
    assert "SN-123" in body
    assert "Técnico Atual" in body
    assert "Cache-Control" not in body
