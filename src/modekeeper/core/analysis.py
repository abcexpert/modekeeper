from __future__ import annotations

from dataclasses import dataclass
from statistics import mean, median

from modekeeper.telemetry.models import TelemetrySample


@dataclass
class SignalSet:
    drift: bool
    burst: bool
    straggler: bool
    gpu_saturated: bool
    incident: bool
    stable: bool
    notes: list[str]

    def to_dict(self) -> dict:
        return {
            "drift": self.drift,
            "burst": self.burst,
            "straggler": self.straggler,
            "gpu_saturated": self.gpu_saturated,
            "incident": self.incident,
            "stable": self.stable,
            "notes": self.notes,
        }


def analyze_signals(samples: list[TelemetrySample]) -> dict:
    if not samples:
        return SignalSet(False, False, False, False, False, True, ["no_samples"]).to_dict()

    losses = [s.loss for s in samples if s.loss is not None]
    latencies = [s.latency_ms for s in samples]
    worker_max = [max(s.worker_latencies_ms) for s in samples]
    worker_med = [median(s.worker_latencies_ms) for s in samples]

    if losses:
        loss_start = mean(losses[: max(1, len(losses) // 4)])
        loss_end = mean(losses[-max(1, len(losses) // 4) :])
        drift = loss_end > loss_start * 1.15
    else:
        drift = False

    lat_med = median(latencies)
    burst = max(latencies) > lat_med * 1.5

    straggler = mean(worker_max) > mean(worker_med) * 1.6

    gpu_utils = [
        float(s.gpu_util_pct)
        for s in samples
        if getattr(s, "gpu_util_pct", None) is not None
    ]
    gpu_mems = [
        float(s.gpu_mem_util_pct)
        for s in samples
        if getattr(s, "gpu_mem_util_pct", None) is not None
    ]
    gpu_saturated = False
    if gpu_utils:
        gpu_saturated = max(gpu_utils) >= 90.0
    if gpu_mems:
        gpu_saturated = gpu_saturated or (max(gpu_mems) >= 90.0)

    notes: list[str] = []
    if drift:
        notes.append("loss_drift")
    elif not losses:
        notes.append("loss_missing")
    if burst:
        notes.append("latency_burst")
    if straggler:
        notes.append("straggler_detected")
    if gpu_saturated:
        notes.append("gpu_saturated")

    incident = drift or burst or straggler or gpu_saturated
    stable = not incident
    return SignalSet(drift, burst, straggler, gpu_saturated, incident, stable, notes).to_dict()
