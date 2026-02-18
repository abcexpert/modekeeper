from __future__ import annotations

import json

from modekeeper.core.cost_model import get_default_cost_model
from modekeeper.core.value_summary import build_value_summary
from modekeeper.telemetry.models import TelemetrySample


def _sample_points() -> list[TelemetrySample]:
    return [
        TelemetrySample(
            timestamp_ms=0,
            loss=1.0,
            latency_ms=100.0,
            throughput=1000.0,
            worker_latencies_ms=[100.0],
        ),
        TelemetrySample(
            timestamp_ms=1000,
            loss=1.1,
            latency_ms=200.0,
            throughput=950.0,
            worker_latencies_ms=[200.0],
        ),
        TelemetrySample(
            timestamp_ms=2000,
            loss=1.2,
            latency_ms=300.0,
            throughput=900.0,
            worker_latencies_ms=[300.0],
        ),
    ]


def test_build_value_summary_is_deterministic() -> None:
    samples = _sample_points()
    signals = {"burst": True}
    opportunity = {"opportunity_hours_est": 1.25}
    cost_model = get_default_cost_model()

    left = build_value_summary(
        samples=samples,
        signals=signals,
        opportunity=opportunity,
        cost_model=cost_model,
    )
    right = build_value_summary(
        samples=samples,
        signals=signals,
        opportunity=opportunity,
        cost_model=cost_model,
    )

    assert left == right


def test_build_value_summary_has_no_raw_samples_or_observation_lists() -> None:
    value_summary = build_value_summary(
        samples=_sample_points(),
        signals={},
        opportunity={"opportunity_hours_est": 0.5},
        cost_model=get_default_cost_model(),
    )

    payload = json.dumps(value_summary, sort_keys=True)
    assert "samples" not in payload

    for key, value in value_summary.items():
        if key == "assumptions":
            assert isinstance(value, list)
            assert all(isinstance(item, str) for item in value)
            continue
        assert not isinstance(value, list)
