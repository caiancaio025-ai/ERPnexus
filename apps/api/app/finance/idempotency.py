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
    return fingerprint_mapping(payload.model_dump(mode="json"))
