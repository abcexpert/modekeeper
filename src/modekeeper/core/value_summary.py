from __future__ import annotations

import math

from modekeeper.core.cost_model import CostModelV0
from modekeeper.telemetry.models import TelemetrySample


def _percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return float(ordered[0])
    rank = (len(ordered) - 1) * percentile
    lower = math.floor(rank)
    upper = math.ceil(rank)
    if lower == upper:
        return float(ordered[lower])
    weight = rank - lower
    return float(ordered[lower] * (1.0 - weight) + ordered[upper] * weight)


def build_value_summary(
    *,
    samples: list[TelemetrySample],
    signals: dict,
    opportunity: dict,
    cost_model: CostModelV0,
) -> dict:
    del signals
    opportunity_hours_est = opportunity.get("opportunity_hours_est")
    if isinstance(opportunity_hours_est, (int, float)):
        opportunity_hours_value = float(opportunity_hours_est)
    else:
        opportunity_hours_value = 0.0

    step_times = [
        float(sample.latency_ms)
        for sample in samples
        if isinstance(sample.latency_ms, (int, float))
    ]
    step_time_ms_p50 = _percentile(step_times, 0.50)
    step_time_ms_p95 = _percentile(step_times, 0.95)

    gpus_per_job = cost_model.get("gpus_per_job")
    gpus_multiplier = gpus_per_job if isinstance(gpus_per_job, int) and gpus_per_job > 0 else 1
    usd_per_gpu_hour = cost_model.get("usd_per_gpu_hour")

    gpu_hours_leak_est = round(opportunity_hours_value * float(gpus_multiplier), 6)
    usd_leak_est: float | None = None
    if isinstance(usd_per_gpu_hour, (int, float)):
        usd_leak_est = round(gpu_hours_leak_est * float(usd_per_gpu_hour), 6)

    assumptions: list[str] = [
        "gpu_hours_leak_est = opportunity_hours_est * max(gpus_per_job, 1)",
        "step_time_ms percentiles use sample.latency_ms",
        "usd_leak_est = gpu_hours_leak_est * usd_per_gpu_hour when usd_per_gpu_hour is set",
        "value_summary contains only aggregates and no raw observations",
    ]
    if not isinstance(gpus_per_job, int) or gpus_per_job <= 0:
        assumptions.append("gpus_per_job defaults to 1 when not set")
    if not isinstance(usd_per_gpu_hour, (int, float)):
        assumptions.append("usd_per_gpu_hour not set, usd_leak_est is null")

    return {
        "schema_version": "value_summary.v0",
        "opportunity_hours_est": opportunity.get("opportunity_hours_est"),
        "throughput": {
            "step_time_ms_p50": round(step_time_ms_p50, 6) if step_time_ms_p50 is not None else None,
            "step_time_ms_p95": round(step_time_ms_p95, 6) if step_time_ms_p95 is not None else None,
        },
        "cost_model": {
            "schema_version": cost_model.get("schema_version"),
            "usd_per_gpu_hour": usd_per_gpu_hour,
            "gpus_per_job": gpus_per_job,
        },
        "value_estimates": {
            "gpu_hours_leak_est": gpu_hours_leak_est,
            "usd_leak_est": usd_leak_est,
        },
        "assumptions": sorted(assumptions),
    }
