from fastapi.testclient import TestClient

from app.main import app


client = TestClient(app)


def test_response_generates_request_id() -> None:
    response = client.get("/health/live")

    assert response.status_code == 200

    request_id = response.headers.get("X-Request-ID")

    assert request_id is not None
    assert len(request_id) >= 16


def test_response_preserves_valid_request_id() -> None:
    request_id = "audit-request-1234567890"

    response = client.get(
        "/health/live",
        headers={"X-Request-ID": request_id},
    )

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == request_id


def test_invalid_request_id_is_replaced() -> None:
    response = client.get(
        "/health/live",
        headers={"X-Request-ID": "invalid request id\n"},
    )

    assert response.status_code == 200

    returned = response.headers["X-Request-ID"]

    assert returned != "invalid request id\n"
    assert len(returned) >= 16

def test_query_string_is_not_exposed_in_request_log(caplog) -> None:
    import logging

    caplog.set_level(logging.INFO, logger="uvicorn.error")

    response = client.get(
        "/health/live?token=super-secret-value",
        headers={"X-Request-ID": "audit-request-log-123456"},
    )

    assert response.status_code == 200

    messages = [record.getMessage() for record in caplog.records]

    assert any(
        "request_id=audit-request-log-123456" in message
        for message in messages
    )

    assert all(
        "super-secret-value" not in message
        for message in messages
    )