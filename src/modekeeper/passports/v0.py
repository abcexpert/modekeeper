from __future__ import annotations

import json
from dataclasses import dataclass
from importlib import resources
from pathlib import Path

CANONICAL_CHORD_IDS = {
    "NORMAL-HOLD",
    "DRIFT-RETUNE",
    "BURST-ABSORB",
    "INPUT-STRAGGLER",
    "RECOVER",
    "RELOCK",
}
REQUIRED_LIMIT_KEYS = {
    "cooldown_s",
    "max_delta_per_step",
    "relock_stable_intervals",
}


class PassportValidationError(ValueError):
    """Raised when passport.v0 validation fails."""


@dataclass(frozen=True)
class PassportV0:
    schema_version: str
    name: str
    description: str
    allowed_chords: list[str]
    allowed_actuators_hot: list[str]
    allowed_actuators_cold: list[str]
    limits: dict[str, object]
    invariants: list[str]
    cooldowns: dict[str, object]
    gates: dict[str, object]



def _expect_dict(value: object, *, path: str) -> dict:
    if not isinstance(value, dict):
        raise PassportValidationError(f"{path} must be an object")
    return value



def _expect_list_of_str(value: object, *, path: str) -> list[str]:
    if not isinstance(value, list):
        raise PassportValidationError(f"{path} must be an array of strings")
    result: list[str] = []
    for idx, item in enumerate(value):
        if not isinstance(item, str) or not item.strip():
            raise PassportValidationError(f"{path}[{idx}] must be a non-empty string")
        result.append(item)
    return result



def _validate_knob_limits(limits: dict[str, object]) -> None:
    knob_limits = limits.get("knob_limits")
    if knob_limits is None:
        return
    if not isinstance(knob_limits, dict):
        raise PassportValidationError("limits.knob_limits must be an object")

    for knob, bound in knob_limits.items():
        if not isinstance(knob, str) or not knob.strip():
            raise PassportValidationError("limits.knob_limits keys must be non-empty strings")
        if not isinstance(bound, dict):
            raise PassportValidationError(f"limits.knob_limits.{knob} must be an object")
        min_v = bound.get("min")
        max_v = bound.get("max")
        if not isinstance(min_v, int):
            raise PassportValidationError(f"limits.knob_limits.{knob}.min must be int")
        if not isinstance(max_v, int):
            raise PassportValidationError(f"limits.knob_limits.{knob}.max must be int")
        if min_v > max_v:
            raise PassportValidationError(
                f"limits.knob_limits.{knob}.min must be <= limits.knob_limits.{knob}.max"
            )



def validate_passport(payload: dict[str, object], *, source: str) -> PassportV0:
    schema_version = payload.get("schema_version")
    if schema_version != "passport.v0":
        raise PassportValidationError(
            f"{source}: schema_version must be 'passport.v0'"
        )

    name = payload.get("name")
    if not isinstance(name, str) or not name.strip():
        raise PassportValidationError(f"{source}: name is required and must be non-empty string")

    allowed_chords = _expect_list_of_str(payload.get("allowed_chords"), path="allowed_chords")
    if not allowed_chords:
        raise PassportValidationError(f"{source}: allowed_chords must not be empty")

    invalid_chords = [ch for ch in allowed_chords if ch not in CANONICAL_CHORD_IDS]
    if invalid_chords:
        allowed = ", ".join(sorted(CANONICAL_CHORD_IDS))
        bad = ", ".join(invalid_chords)
        raise PassportValidationError(
            f"{source}: allowed_chords contains unknown IDs ({bad}); expected canonical IDs: {allowed}"
        )

    allowed_actuators = _expect_dict(payload.get("allowed_actuators"), path="allowed_actuators")
    hot = _expect_list_of_str(allowed_actuators.get("hot"), path="allowed_actuators.hot")
    cold = _expect_list_of_str(allowed_actuators.get("cold"), path="allowed_actuators.cold")

    limits = _expect_dict(payload.get("limits"), path="limits")
    missing_limits = [key for key in sorted(REQUIRED_LIMIT_KEYS) if key not in limits]
    if missing_limits:
        missing = ", ".join(missing_limits)
        raise PassportValidationError(f"{source}: limits missing required keys: {missing}")

    cooldown_s = limits.get("cooldown_s")
    max_delta_per_step = limits.get("max_delta_per_step")
    relock_stable_intervals = limits.get("relock_stable_intervals")
    if not isinstance(cooldown_s, int) or cooldown_s < 0:
        raise PassportValidationError(f"{source}: limits.cooldown_s must be int >= 0")
    if not isinstance(max_delta_per_step, int) or max_delta_per_step < 0:
        raise PassportValidationError(f"{source}: limits.max_delta_per_step must be int >= 0")
    if not isinstance(relock_stable_intervals, int) or relock_stable_intervals < 1:
        raise PassportValidationError(f"{source}: limits.relock_stable_intervals must be int >= 1")

    _validate_knob_limits(limits)

    description_raw = payload.get("description", "")
    description = description_raw if isinstance(description_raw, str) else ""

    invariants_raw = payload.get("invariants", [])
    invariants = _expect_list_of_str(invariants_raw, path="invariants")

    cooldowns_raw = payload.get("cooldowns", {})
    cooldowns = _expect_dict(cooldowns_raw, path="cooldowns")

    gates_raw = payload.get("gates", {})
    gates = _expect_dict(gates_raw, path="gates")

    return PassportV0(
        schema_version="passport.v0",
        name=name,
        description=description,
        allowed_chords=allowed_chords,
        allowed_actuators_hot=hot,
        allowed_actuators_cold=cold,
        limits=limits,
        invariants=invariants,
        cooldowns=cooldowns,
        gates=gates,
    )



def _load_json_file(path: Path) -> dict[str, object]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise PassportValidationError(f"passport file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise PassportValidationError(f"invalid JSON in {path}: {exc}") from exc

    if not isinstance(payload, dict):
        raise PassportValidationError(f"{path}: top-level JSON must be an object")
    return payload



def list_templates() -> list[str]:
    package = resources.files("modekeeper.passports.templates")
    names: list[str] = []
    for entry in package.iterdir():
        if entry.name.endswith(".json") and entry.is_file():
            names.append(entry.name[:-5])
    return sorted(names)



def load_template(name: str) -> PassportV0:
    template_name = name.strip()
    if not template_name:
        raise PassportValidationError("template name must be non-empty")

    candidate = resources.files("modekeeper.passports.templates").joinpath(
        f"{template_name}.json"
    )
    if not candidate.is_file():
        known = ", ".join(list_templates())
        raise PassportValidationError(
            f"unknown template '{template_name}'; available: {known}"
        )

    payload = json.loads(candidate.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise PassportValidationError(
            f"template {template_name}: top-level JSON must be an object"
        )
    return validate_passport(payload, source=f"template:{template_name}")



def load_passport(path: Path) -> PassportV0:
    payload = _load_json_file(path)
    return validate_passport(payload, source=str(path))
