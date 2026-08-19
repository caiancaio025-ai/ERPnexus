import asyncio
import sys
from collections.abc import Callable
from typing import Any


def pytest_asyncio_loop_factories(
    config: Any,
    item: Any,
) -> dict[str, Callable[[], asyncio.AbstractEventLoop]]:
    del config, item

    if sys.platform == "win32":
        return {
            "selector": asyncio.SelectorEventLoop,
        }

    return {
        "default": asyncio.new_event_loop,
    }
