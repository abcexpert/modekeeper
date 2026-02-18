"""Canonical JSON serialization for signed license payloads."""

from __future__ import annotations

import json


def canonical_json_bytes(obj: dict) -> bytes:
    """Serialize object to deterministic UTF-8 JSON bytes."""
    return json.dumps(
        obj,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
