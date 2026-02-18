from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

CATALOG_SCHEMA_VERSION = "chord_catalog.v1"
VALIDATE_SCHEMA_VERSION = "chords_validate.v0"
_REQUIRED_CHORD_KEYS = (
    "id",
    "intent",
    "risk_tier",
    "required_signals",
    "invariants",
    "knobs_touched",
)
_OPTIONAL_CHORD_KEYS = ("cooldown_ms", "budget")
_ALLOWED_CHORD_KEYS = frozenset((*_REQUIRED_CHORD_KEYS, *_OPTIONAL_CHORD_KEYS))


def _is_list_of_str(value: object) -> bool:
    return isinstance(value, list) and all(isinstance(item, str) for item in value)


def validate_catalog_dict(catalog: dict, source: str) -> list[str]:
    errors: list[str] = []
    if not isinstance(catalog, dict):
        return [f"{source}: top-level JSON must be an object"]

    top_unknown_keys = sorted(set(catalog.keys()) - {"schema_version", "chords"})
    for key in top_unknown_keys:
        errors.append(f"{source}: unknown top-level field '{key}'")

    schema_version = catalog.get("schema_version")
    if schema_version != CATALOG_SCHEMA_VERSION:
        errors.append(f"{source}: schema_version must be '{CATALOG_SCHEMA_VERSION}'")

    chords = catalog.get("chords")
    if not isinstance(chords, list):
        errors.append(f"{source}: chords must be an array")
        return errors

    seen_ids: set[str] = set()
    for index, item in enumerate(chords):
        path = f"{source}: chords[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{path} must be an object")
            continue

        unknown_keys = sorted(set(item.keys()) - _ALLOWED_CHORD_KEYS)
        for key in unknown_keys:
            errors.append(f"{path}: unknown field '{key}'")

        for key in _REQUIRED_CHORD_KEYS:
            if key not in item:
                errors.append(f"{path}: missing required field '{key}'")

        chord_id = item.get("id")
        if isinstance(chord_id, str):
            if chord_id in seen_ids:
                errors.append(f"{path}: duplicate chord id '{chord_id}'")
            else:
                seen_ids.add(chord_id)
        else:
            errors.append(f"{path}: id must be string")

        intent = item.get("intent")
        if not isinstance(intent, str):
            errors.append(f"{path}: intent must be string")

        risk_tier = item.get("risk_tier")
        if not isinstance(risk_tier, str):
            errors.append(f"{path}: risk_tier must be string")

        required_signals = item.get("required_signals")
        if not _is_list_of_str(required_signals):
            errors.append(f"{path}: required_signals must be array of strings")

        invariants = item.get("invariants")
        if not _is_list_of_str(invariants):
            errors.append(f"{path}: invariants must be array of strings")

        knobs_touched = item.get("knobs_touched")
        if not _is_list_of_str(knobs_touched):
            errors.append(f"{path}: knobs_touched must be array of strings")

        if "cooldown_ms" in item and not isinstance(item.get("cooldown_ms"), int):
            errors.append(f"{path}: cooldown_ms must be int")

        if "budget" in item and not isinstance(item.get("budget"), dict):
            errors.append(f"{path}: budget must be object")

    return errors


def validate_catalog_file(path: Path) -> dict:
    source = str(path)
    errors: list[str] = []
    payload: object = {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        errors.append(f"{source}: file not found")
    except json.JSONDecodeError as exc:
        errors.append(f"{source}: invalid JSON: {exc}")

    chord_count = 0
    chord_ids: list[str] = []
    if isinstance(payload, dict):
        chords = payload.get("chords")
        if isinstance(chords, list):
            chord_count = len(chords)
            chord_ids = sorted(
                {
                    item.get("id")
                    for item in chords
                    if isinstance(item, dict) and isinstance(item.get("id"), str)
                }
            )

    if errors:
        return {
            "schema_version": VALIDATE_SCHEMA_VERSION,
            "ok": False,
            "errors": errors,
            "chord_count": chord_count,
            "chord_ids": chord_ids,
        }

    if isinstance(payload, dict):
        errors.extend(validate_catalog_dict(payload, source=source))
    else:
        errors.append(f"{source}: top-level JSON must be an object")

    return {
        "schema_version": VALIDATE_SCHEMA_VERSION,
        "ok": len(errors) == 0,
        "errors": errors,
        "chord_count": chord_count,
        "chord_ids": chord_ids,
    }


def load_catalog_file(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"{path}: top-level JSON must be an object")
    errors = validate_catalog_dict(payload, source=str(path))
    if errors:
        raise ValueError("; ".join(errors))
    return payload


@lru_cache(maxsize=1)
def load_default_catalog() -> dict:
    path = Path(__file__).with_name("catalog_v1.json")
    return load_catalog_file(path)
