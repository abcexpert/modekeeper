from __future__ import annotations

from statistics import mean

from modekeeper.telemetry.models import TelemetrySample


def _baseline_window_seconds(samples: list[TelemetrySample]) -> float:
    timestamps = [s.timestamp_ms for s in samples if isinstance(s.timestamp_ms, (int, float))]
    if len(timestamps) < 2:
        return 0.0
    window_ms = max(timestamps) - min(timestamps)
    if window_ms <= 0:
        return 0.0
    return float(window_ms) / 1000.0


def estimate_opportunity(
    samples: list[TelemetrySample],
    signals: dict,
    *,
    gpu_hour_usd: float = 0.0,
    gpu_count: int = 0,
) -> dict:
    active_signals = [
        key
        for key in ("drift", "burst", "straggler", "gpu_saturated")
        if signals.get(key) is True
    ]
    opportunity_fraction = min(0.30, 0.05 * len(active_signals))

    baseline_window_s = _baseline_window_seconds(samples)
    throughput_values = [
        float(s.throughput)
        for s in samples
        if isinstance(s.throughput, (int, float)) and s.throughput > 0
    ]
    throughput_avg = mean(throughput_values) if throughput_values else 0.0

    opportunity_hours_est = (baseline_window_s / 3600.0) * opportunity_fraction
    opportunity_tokens_est = throughput_avg * baseline_window_s * opportunity_fraction
    opportunity_usd_est = opportunity_hours_est * float(gpu_hour_usd) * max(int(gpu_count), 0)

    def _round(value: float) -> float:
        return round(float(value), 6)

    assumptions = {
        "model": "heuristic_v1",
        "active_signals": active_signals,
        "opportunity_fraction": _round(opportunity_fraction),
        "baseline_window_s": _round(baseline_window_s),
        "throughput_avg_per_s": _round(throughput_avg),
        "throughput_unit": "tokens_per_sec (assumed)",
        "gpu_hour_usd": float(gpu_hour_usd),
        "gpu_count": int(gpu_count),
        "formulas": {
            "opportunity_hours_est": "baseline_window_s/3600 * opportunity_fraction",
            "opportunity_tokens_est": "throughput_avg_per_s * baseline_window_s * opportunity_fraction",
            "opportunity_usd_est": "opportunity_hours_est * gpu_hour_usd * gpu_count",
        },
        "notes": "throughput_avg_per_s=0 when source lacks throughput",
    }

    return {
        "opportunity_hours_est": _round(opportunity_hours_est),
        "opportunity_tokens_est": _round(opportunity_tokens_est),
        "opportunity_usd_est": _round(opportunity_usd_est),
        "opportunity_assumptions": assumptions,
    }
