from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_live() -> None:
    response = client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ready() -> None:
    response = client.get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_version_identifies_installed_release_without_caching() -> None:
    response = client.get("/health/version")
    assert response.status_code == 200
    assert response.json()["version"] == "48"
    assert response.headers["Cache-Control"] == "no-store"
