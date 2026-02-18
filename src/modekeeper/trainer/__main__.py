"""Runtime loop for a minimal trainer demo container."""

from __future__ import annotations

import json
import math
import os
import time
from datetime import datetime, timezone

from .knobs import parse_downward_annotations

_DEFAULT_ANNOTATIONS_FILE = "/etc/podinfo/annotations"
_DEFAULT_LOOP_INTERVAL_S = 2.0


def _read_knobs(path: str) -> dict[str, str]:
    try:
        with open(path, "r", encoding="utf-8") as handle:
            text = handle.read()
    except OSError:
        return {}
    return parse_downward_annotations(text)


def _to_positive_int(value: str | None, default: int = 1) -> int:
    if value is None:
        return default
    value = value.strip()
    if not value.isdigit():
        return default
    parsed = int(value)
    return parsed if parsed >= 1 else default


def _to_positive_float(value: str | None, default: float) -> float:
    if value is None:
        return default
    try:
        parsed = float(str(value).strip())
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def _sorted_knobs(knobs: dict[str, str]) -> dict[str, str]:
    return {key: knobs[key] for key in sorted(knobs)}


def _knobs_kv(knobs: dict[str, str]) -> str:
    return " ".join(f"{key}={value}" for key, value in _sorted_knobs(knobs).items())


def _step_time_ms(knobs: dict[str, str], now_s: int) -> int:
    conc = _to_positive_int(knobs.get("concurrency"), default=1)
    pref = _to_positive_int(knobs.get("dataloader_prefetch_factor"), default=1)

    base_ms = 2000 - (conc - 1) * 250 - (pref - 1) * 250
    if base_ms < 500:
        base_ms = 500

    lat_ms = base_ms
    if conc <= 2 and pref <= 2 and now_s % 3 == 0:
        lat_ms = base_ms + 2000
    return lat_ms


def _demo_loss(step: int) -> float:
    base = 1.5 * math.exp(-0.015 * step)
    noise = 0.01 * math.sin(step / 7.0)
    value = base + noise
    return round(value, 6)


def _demo_throughput(step: int, knobs: dict[str, str]) -> float:
    conc = _to_positive_int(knobs.get("concurrency"), default=1)
    pref = _to_positive_int(knobs.get("dataloader_prefetch_factor"), default=1)
    knob_bonus = max(0, conc - 1) * 4.0 + max(0, pref - 1) * 2.0
    oscillation = 6.0 * math.sin(step / 11.0)
    value = 120.0 + knob_bonus + oscillation
    return round(max(1.0, value), 3)


def main() -> int:
    annotations_path = os.environ.get("MODEKEEPER_ANNOTATIONS_FILE", _DEFAULT_ANNOTATIONS_FILE)
    loop_interval_s = _to_positive_float(
        os.environ.get("MODEKEEPER_LOOP_INTERVAL_S"),
        default=_DEFAULT_LOOP_INTERVAL_S,
    )
    step = 0

    while True:
        knobs = _read_knobs(annotations_path)
        sorted_knobs = _sorted_knobs(knobs)
        now_s = int(time.time())
        ts = datetime.fromtimestamp(now_s, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        step_time_ms = _step_time_ms(knobs, now_s)
        throughput = _demo_throughput(step, knobs)
        payload = {
            "ts": ts,
            "step": step,
            "event": "knobs_snapshot",
            "loss": _demo_loss(step),
            "throughput": throughput,
            "step_time_ms": step_time_ms,
            "annotations_file": annotations_path,
            "knobs": sorted_knobs,
            "knobs_kv": _knobs_kv(knobs),
        }
        print(json.dumps(payload, separators=(",", ":")), flush=True)

        time.sleep(loop_interval_s)
        step += 1


if __name__ == "__main__":
    raise SystemExit(main())
