from unittest.mock import AsyncMock, MagicMock

import pytest

from app.customers.service import list_customers_page


@pytest.mark.asyncio
async def test_customer_page_clamps_requested_page_and_applies_limit_offset():
    db = AsyncMock()
    db.scalar.return_value = 270
    scalars_result = MagicMock()
    scalars_result.all.return_value = [MagicMock(id=201)]
    db.scalars.return_value = scalars_result

    result = await list_customers_page(
        db,
        page=9,
        page_size=100,
        company_code="universo_eletronica",
        search=None,
    )

    assert result.page == 3
    assert result.pages == 3
    assert result.total == 270
    assert result.page_size == 100
    statement = db.scalars.await_args.args[0]
    assert statement._limit_clause.value == 100
    assert statement._offset_clause.value == 200


@pytest.mark.asyncio
async def test_customer_page_empty_dataset_stays_on_page_one():
    db = AsyncMock()
    db.scalar.return_value = 0
    scalars_result = MagicMock()
    scalars_result.all.return_value = []
    db.scalars.return_value = scalars_result

    result = await list_customers_page(
        db,
        page=4,
        page_size=100,
        company_code=None,
        search=" inexistente ",
    )

    assert result.page == 1
    assert result.pages == 1
    assert result.total == 0
    statement = db.scalars.await_args.args[0]
    assert statement._offset_clause.value == 0


@pytest.mark.asyncio
async def test_customer_page_executes_one_count_and_one_page_query():
    db = AsyncMock()
    db.scalar.return_value = 12
    scalars_result = MagicMock()
    scalars_result.all.return_value = []
    db.scalars.return_value = scalars_result

    await list_customers_page(
        db,
        page=1,
        page_size=100,
        company_code=None,
        search=None,
    )

    assert db.scalar.await_count == 1
    assert db.scalars.await_count == 1
