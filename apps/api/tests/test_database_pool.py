import asyncio
import os
import time
from collections.abc import AsyncIterator
from typing import Protocol, cast

import pytest
from sqlalchemy import text

from app.core.config import settings
from app.core.db import engine, session_factory


class PoolMetrics(Protocol):
    def checkedout(self) -> int: ...

    def status(self) -> str: ...


def pool_metrics() -> PoolMetrics:
    return cast(PoolMetrics, engine.pool)


async def execute_database_query(index: int) -> tuple[int, float]:
    started_at = time.perf_counter()

    async with session_factory() as session:
        result = await session.scalar(text("SELECT 1"))

    elapsed = time.perf_counter() - started_at
    print(f"Consulta {index}: {elapsed:.3f}s")

    return int(result or 0), elapsed


@pytest.fixture(autouse=True)
async def dispose_engine_after_test() -> AsyncIterator[None]:
    yield
    await engine.dispose()


@pytest.mark.asyncio
async def test_single_database_query() -> None:
    result, elapsed = await execute_database_query(1)

    print(f"\nConsulta única: {elapsed:.3f}s")

    assert result == 1
    assert pool_metrics().checkedout() == 0


@pytest.mark.asyncio
async def test_database_pool_returns_connections_after_concurrent_queries() -> None:
    pool_capacity = settings.db_pool_size + settings.db_max_overflow
    started_at = time.perf_counter()

    results = await asyncio.gather(
        *(execute_database_query(index) for index in range(1, pool_capacity + 1))
    )

    elapsed = time.perf_counter() - started_at

    print(f"\nLote concorrente: {elapsed:.3f}s")
    print(f"Estado final do pool: {pool_metrics().status()}")

    assert len(results) == pool_capacity
    assert all(result == 1 for result, _ in results)
    assert pool_metrics().checkedout() == 0


@pytest.mark.performance
@pytest.mark.asyncio
async def test_database_connection_performance() -> None:
    if os.getenv("RUN_DB_PERFORMANCE_TESTS") != "1":
        pytest.skip("Defina RUN_DB_PERFORMANCE_TESTS=1 para executar o limite de desempenho.")

    maximum_seconds = float(os.getenv("DB_SINGLE_QUERY_MAX_SECONDS", "5"))
    result, elapsed = await execute_database_query(1)

    assert result == 1
    assert elapsed < maximum_seconds
