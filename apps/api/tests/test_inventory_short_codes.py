"""Regressoes para codigo curto de estoque e compatibilidade QR legado."""
import pytest
from app.inventory.stock_codes import format_stock_code, stock_id_from_query

@pytest.mark.parametrize(("number", "expected"), [(1,"EST-01"),(2,"EST-02"),(9,"EST-09"),(10,"EST-10"),(99,"EST-99"),(100,"EST-100"),(12345,"EST-12345")])
def test_format_stock_code(number, expected):
    assert format_stock_code(number) == expected

@pytest.mark.parametrize("number", [0, -1, 1.5, "1", None])
def test_invalid_id(number):
    with pytest.raises(ValueError):
        format_stock_code(number)

@pytest.mark.parametrize("search", ["EST-01","est-00000001","EST - 01"," EST-1 ","EST-000001"])
def test_old_and_new_qr_search(search):
    assert stock_id_from_query(search) == 1

@pytest.mark.parametrize("search", ["","IGBT 500A", "SN0001", "EST-0", "EST-XYZ"])
def test_non_stock_query(search):
    assert stock_id_from_query(search) is None

def test_short_code_does_not_change_manufacturer_serial():
    from app.inventory.models import InventoryItem
    item = InventoryItem(id=1, stock_code=format_stock_code(1), manufacturer_serial="000000ABC", mode="serialized", quantity=1, name="Inversor", category="inversor", company_code="universo_eletronica", created_by=1)
    assert item.stock_code == "EST-01"
    assert item.manufacturer_serial == "000000ABC"
