from __future__ import annotations

from modekeeper.telemetry.models import TelemetrySample


def _quantile_sorted(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    if len(values) == 1:
        return float(values[0])
    clamped_q = min(max(float(q), 0.0), 1.0)
    index = int(clamped_q * (len(values) - 1))
    return float(values[index])


def _round6(value: float) -> float:
    return round(float(value), 6)


def summarize_latencies(samples: list[TelemetrySample]) -> dict:
    latencies = sorted(float(sample.latency_ms) for sample in samples)
    return {
        "samples": len(samples),
        "p50_ms": _round6(_quantile_sorted(latencies, 0.50)),
        "p95_ms": _round6(_quantile_sorted(latencies, 0.95)),
    }


def build_roi_before_after_summary(
    *,
    baseline_p50_ms: float,
    candidate_p50_ms: float,
    usd_per_gpu_hour: float,
    gpus: int,
    hours_per_month: int,
) -> dict:
    speedup_p50: float | None = None
    if candidate_p50_ms > 0:
        speedup_p50 = baseline_p50_ms / candidate_p50_ms

    usd_saved_per_gpu_hour = 0.0
    if isinstance(speedup_p50, (int, float)) and speedup_p50 > 1.0:
        usd_saved_per_gpu_hour = usd_per_gpu_hour * max(0.0, 1.0 - (1.0 / float(speedup_p50)))

    usd_saved_per_hour = usd_saved_per_gpu_hour * gpus
    usd_saved_per_month = usd_saved_per_hour * hours_per_month

    return {
        "speedup_p50": _round6(speedup_p50) if isinstance(speedup_p50, (int, float)) else None,
        "usd_per_gpu_hour": _round6(usd_per_gpu_hour),
        "gpus": int(gpus),
        "hours_per_month": int(hours_per_month),
        "usd_saved_per_gpu_hour": _round6(usd_saved_per_gpu_hour),
        "usd_saved_per_hour": _round6(usd_saved_per_hour),
        "usd_saved_per_month": _round6(usd_saved_per_month),
    }
