from __future__ import annotations

from pathlib import Path

from modekeeper.core.analysis import analyze_signals
from modekeeper.demo.mk068_demo import run_mk068_demo
from modekeeper.policy.rules import propose_actions
from modekeeper.safety.explain import ExplainLog
from modekeeper.telemetry.collector import TelemetryCollector
from modekeeper.telemetry.sources import SyntheticSource


def run_demo(scenario: str, out_dir: Path, explain: ExplainLog) -> dict:
    source = SyntheticSource(scenario=scenario, duration_ms=60_000)
    collector = TelemetryCollector(source)
    samples = collector.collect()
    signals = analyze_signals(samples)
    proposed = propose_actions(signals)

    explain.emit(
        "demo_summary",
        {"scenario": scenario, "signals": signals, "proposed": [p.to_dict() for p in proposed]},
    )

    report = {
        "scenario": scenario,
        "signals": signals,
        "proposed": [p.to_dict() for p in proposed],
    }
    return report
