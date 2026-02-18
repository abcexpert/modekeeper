from __future__ import annotations

from modekeeper.core.analysis import analyze_signals
from modekeeper.telemetry.models import TelemetrySample


def _quantile_sorted(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    if len(values) == 1:
        return float(values[0])
    clamped_q = min(max(float(q), 0.0), 1.0)
    index = int(clamped_q * (len(values) - 1))
    return float(values[index])


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, float(value)))


def _round6(value: float) -> float:
    return round(float(value), 6)


def estimate_roi(samples: list[TelemetrySample]) -> dict:
    signals = analyze_signals(samples)
    latencies = sorted(float(sample.latency_ms) for sample in samples)

    p50_ms = _quantile_sorted(latencies, 0.50)
    p95_ms = _quantile_sorted(latencies, 0.95)
    max_ms = float(latencies[-1]) if latencies else 0.0

    burst_bound = 0.0
    if p95_ms > 0:
        burst_bound = _clamp((p95_ms - p50_ms) / p95_ms, 0.0, 0.8)

    worker_spreads: list[float] = []
    for sample in samples:
        worker_latencies = sorted(float(value) for value in sample.worker_latencies_ms)
        if not worker_latencies:
            continue
        worker_p50 = _quantile_sorted(worker_latencies, 0.50)
        worker_p95 = _quantile_sorted(worker_latencies, 0.95)
        if worker_p95 <= 0:
            continue
        worker_spreads.append(_clamp((worker_p95 - worker_p50) / worker_p95, 0.0, 0.8))

    worker_spreads.sort()
    straggler_bound = _quantile_sorted(worker_spreads, 0.95) if worker_spreads else 0.0

    has_incident = bool(signals.get("incident"))
    bound = max(burst_bound if signals.get("burst") else 0.0, straggler_bound if signals.get("straggler") else 0.0)
    bound = _clamp(bound if has_incident else 0.0, 0.0, 0.8)

    low = _round6(bound * 0.5)
    high = _round6(bound)

    notes: list[str] = []
    signal_notes = signals.get("notes")
    if isinstance(signal_notes, list):
        notes.extend(str(note) for note in signal_notes if isinstance(note, str))
    if not has_incident:
        low = 0.0
        high = 0.0
        notes.append("stable")
    if not notes:
        notes.append("roi_estimate_heuristic")

    return {
        "schema_version": "roi_estimate.v0",
        "summary": {
            "p50_ms": _round6(p50_ms),
            "p95_ms": _round6(p95_ms),
            "max_ms": _round6(max_ms),
            "samples": len(samples),
            "signals": signals,
        },
        "potential": {
            "speedup_pct_range": [low, high],
            "latency_reduction_pct_range": [low, high],
        },
        "notes": notes,
    }
