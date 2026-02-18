from __future__ import annotations

from pytest import approx

from modekeeper.core.opportunity import estimate_opportunity
from modekeeper.telemetry.models import TelemetrySample


def test_estimate_opportunity_heuristic() -> None:
    samples = [
        TelemetrySample(
            timestamp_ms=0,
            loss=1.0,
            latency_ms=120.0,
            throughput=1000.0,
            worker_latencies_ms=[120.0],
        ),
        TelemetrySample(
            timestamp_ms=10_000,
            loss=1.1,
            latency_ms=130.0,
            throughput=1200.0,
            worker_latencies_ms=[130.0],
        ),
    ]
    signals = {
        "drift": True,
        "burst": False,
        "straggler": False,
        "gpu_saturated": False,
    }

    report = estimate_opportunity(samples, signals, gpu_hour_usd=2.0, gpu_count=4)

    raw_hours = (10.0 / 3600.0) * 0.05
    expected_hours = round(raw_hours, 6)
    expected_tokens = round(1100.0 * 10.0 * 0.05, 6)
    expected_usd = round(raw_hours * 2.0 * 4.0, 6)

    assert report["opportunity_hours_est"] == approx(expected_hours)
    assert report["opportunity_tokens_est"] == approx(expected_tokens)
    assert report["opportunity_usd_est"] == approx(expected_usd)
    assert report["opportunity_assumptions"]["active_signals"] == ["drift"]
