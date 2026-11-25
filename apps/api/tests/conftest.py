"""Shared pytest configuration for Nexus."""

import os
from uuid import uuid4

import httpx
import pytest
import pytest_asyncio
from sqlalchemy.engine import make_url


@pytest_asyncio.fixture
async def postgres_client():
    """Real authenticated HTTP requests, only against an explicitly selected test DB.

    No production database is created, truncated or reset by this fixture. The
    caller must prepare a disposable, migrated database whose name ends in _test.
    """
    from app.auth.models import User
    from app.auth.security import hash_password
    from app.core.config import settings
    from app.core.db import engine, session_factory
    from app.main import app

    url = os.getenv("SENTICO_TEST_DATABASE_URL")
    if not url:
        pytest.skip("PostgreSQL isolado não configurado (SENTICO_TEST_DATABASE_URL).")
    target = make_url(url)
    if url != settings.database_url or not (target.database or "").endswith("_test"):
        pytest.fail("A suíte de integração exige DATABASE_URL igual ao banco *_test explícito.")
    username = f"test_{uuid4().hex[:16]}"
    password = "Only-in-isolated-V48-tests!"
    async with session_factory() as db:
        db.add(User(
            name="Gestor integração V48", email=f"{username}@example.invalid",
            username=username, password_hash=hash_password(password), role="gestao",
            modules=[], is_active=True,
        ))
        await db.commit()
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver", timeout=30) as client:
            response = await client.post("/auth/login", json={"identifier": username, "password": password})
            assert response.status_code == 200, response.text
            yield client
    finally:
        await engine.dispose()
