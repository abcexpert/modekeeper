from __future__ import annotations

from dataclasses import dataclass


@dataclass
class TelemetrySample:
    timestamp_ms: int
    loss: float | None
    latency_ms: float
    throughput: float
    worker_latencies_ms: list[float]
    step: int | None = None
    node: str | None = None
    gpu_model: str | None = None
    # Optional GPU telemetry (when available in source)
    gpu_util_pct: float | None = None
    gpu_mem_util_pct: float | None = None
