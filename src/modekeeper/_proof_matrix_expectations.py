from __future__ import annotations

from typing import Final

PROOF_SCENARIO_ORDER: Final[tuple[str, ...]] = (
    "replica_overprovisioning",
    "cpu_pressure",
    "memory_pressure",
)

PROOF_MATRIX_EXPECTATIONS: Final[dict[str, dict[str, object]]] = {
    "replica_overprovisioning": {
        "signal_flags": {"drift": True, "burst": False},
        "note": "loss_drift",
        "knobs": {"grad_accum_steps", "microbatch_size"},
    },
    "cpu_pressure": {
        "signal_flags": {"drift": False, "burst": True},
        "note": "latency_burst",
        "knobs": {"dataloader_prefetch_factor", "concurrency"},
    },
    "memory_pressure": {
        "signal_flags": {"drift": True, "burst": True},
        "note": "loss_drift",
        "knobs": {
            "grad_accum_steps",
            "microbatch_size",
            "dataloader_prefetch_factor",
            "concurrency",
        },
    },
}
