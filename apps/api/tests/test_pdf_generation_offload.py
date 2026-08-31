import ast
from pathlib import Path

import pytest


CASES = (
    (Path("app/commercial/router.py"), "equipment_label", "commercial_label_pdf"),
    (Path("app/laboratory/router.py"), "work_order_label_pdf", "label_pdf"),
    (Path("app/laboratory/router.py"), "quote_pdf_endpoint", "quote_pdf"),
)


def _async_function(tree: ast.AST, name: str) -> ast.AsyncFunctionDef:
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef) and node.name == name:
            return node
    raise AssertionError(f"async endpoint {name!r} not found")


@pytest.mark.parametrize("router_path,endpoint_name,generator_name", CASES)
def test_pdf_generation_is_offloaded_from_event_loop(
    router_path: Path,
    endpoint_name: str,
    generator_name: str,
) -> None:
    tree = ast.parse(router_path.read_text(encoding="utf-8"))
    endpoint = _async_function(tree, endpoint_name)

    direct_calls = [
        node
        for node in ast.walk(endpoint)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == generator_name
    ]
    assert direct_calls == []

    offloaded = False
    for node in ast.walk(endpoint):
        if not isinstance(node, ast.Await) or not isinstance(node.value, ast.Call):
            continue
        call = node.value
        if not (
            isinstance(call.func, ast.Attribute)
            and isinstance(call.func.value, ast.Name)
            and call.func.value.id == "asyncio"
            and call.func.attr == "to_thread"
            and call.args
        ):
            continue
        first_arg = call.args[0]
        if isinstance(first_arg, ast.Name) and first_arg.id == generator_name:
            offloaded = True
            break

    assert offloaded, f"{generator_name} must run via await asyncio.to_thread(...)"
