from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

from pydantic import BaseModel


def fingerprint_mapping(data: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        data,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def finance_request_fingerprint(payload: BaseModel) -> str:
    data = payload.model_dump(mode="json")
    # Adding optional documentary fields must not invalidate keys recorded by
    # clients before those fields existed.
    for field in ("exit_invoice", "work_order_version"):
        if data.get(field) is None:
            data.pop(field, None)
    return fingerprint_mapping(data)
