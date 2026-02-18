from __future__ import annotations

from typing import Literal, TypedDict


class CostModelV0(TypedDict):
    schema_version: Literal["cost_model.v0"]
    usd_per_gpu_hour: float | None
    gpus_per_job: int | None
    notes: str


def get_default_cost_model() -> CostModelV0:
    return {
        "schema_version": "cost_model.v0",
        "usd_per_gpu_hour": None,
        "gpus_per_job": None,
        "notes": "Estimate leak as opportunity_hours * gpus_per_job * usd_per_gpu_hour.",
    }
