from unittest.mock import AsyncMock, MagicMock

import pytest

from pathlib import Path
from app.customers.service import (
    list_customer_documents_page,
    list_customer_equipment_page,
    list_customer_notes_page,
    list_customer_quotes_page,
    list_customer_work_orders_page,
)


def _mapping_result(items):
    result = MagicMock()
    mappings = MagicMock()
    mappings.all.return_value = items
    result.mappings.return_value = mappings
    return result


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("loader", "expected_total", "requested_page", "page_size", "expected_page", "expected_offset"),
    [
        (list_customer_equipment_page, 88, 9, 25, 4, 75),
        (list_customer_work_orders_page, 88, 5, 25, 4, 75),
        (list_customer_quotes_page, 68, 4, 25, 3, 50),
    ],
)
async def test_customer_relation_pages_clamp_and_use_two_queries(
    loader,
    expected_total,
    requested_page,
    page_size,
    expected_page,
    expected_offset,
):
    db = AsyncMock()
    db.scalar.return_value = expected_total
    db.execute.return_value = _mapping_result([])

    result = await loader(
        db,
        customer_id=541,
        page=requested_page,
        page_size=page_size,
    )

    assert result.total == expected_total
    assert result.page == expected_page
    assert result.page_size == page_size
    assert result.pages == expected_page
    assert result.items == []
    db.scalar.assert_awaited_once()
    db.execute.assert_awaited_once()

    statement = db.execute.await_args.args[0]
    assert statement._limit_clause.value == page_size
    assert statement._offset_clause.value == expected_offset


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "loader",
    [list_customer_notes_page, list_customer_documents_page],
)
async def test_customer_simple_relation_pages_handle_empty_dataset(loader):
    db = AsyncMock()
    db.scalar.return_value = 0
    scalars_result = MagicMock()
    scalars_result.all.return_value = []
    db.scalars.return_value = scalars_result

    result = await loader(
        db,
        customer_id=999999,
        page=7,
        page_size=50,
    )

    assert result.total == 0
    assert result.page == 1
    assert result.pages == 1
    assert result.items == []
    db.scalar.assert_awaited_once()
    db.scalars.assert_awaited_once()
    statement = db.scalars.await_args.args[0]
    assert statement._limit_clause.value == 50
    assert statement._offset_clause.value == 0


def test_customer_documents_page_route_precedes_document_id_route():
    router_source = Path("app/customers/router.py").read_text(encoding="utf-8")
    page_index = router_source.index('@router.get("/{customer_id}/documents/page"')
    document_index = router_source.index('@router.get("/{customer_id}/documents/{document_id}"')
    assert page_index < document_index
