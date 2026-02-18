from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from modekeeper.core.analysis import analyze_signals
from modekeeper.policy.actions import Action
from modekeeper.policy.rules import ChordPlannerState, propose_actions
from modekeeper.telemetry.models import TelemetrySample


@dataclass(frozen=True)
class DemoPhase:
    name: str
    samples: tuple[TelemetrySample, ...]


def _sample(
    timestamp_ms: int,
    *,
    loss: float,
    latency_ms: float,
    throughput: float,
    workers: tuple[float, float, float, float],
) -> TelemetrySample:
    return TelemetrySample(
        timestamp_ms=timestamp_ms,
        loss=loss,
        latency_ms=latency_ms,
        throughput=throughput,
        worker_latencies_ms=list(workers),
    )


def _build_phases() -> list[DemoPhase]:
    return [
        DemoPhase(
            name="NORMAL",
            samples=(
                _sample(0, loss=1.00, latency_ms=100.0, throughput=1020.0, workers=(98.0, 101.0, 99.0, 102.0)),
                _sample(1, loss=1.01, latency_ms=101.0, throughput=1018.0, workers=(99.0, 102.0, 100.0, 103.0)),
                _sample(2, loss=1.00, latency_ms=99.0, throughput=1021.0, workers=(97.0, 100.0, 98.0, 101.0)),
                _sample(3, loss=1.01, latency_ms=100.0, throughput=1019.0, workers=(98.0, 100.0, 99.0, 102.0)),
            ),
        ),
        DemoPhase(
            name="DRIFT",
            samples=(
                _sample(10, loss=1.00, latency_ms=100.0, throughput=1010.0, workers=(98.0, 101.0, 99.0, 100.0)),
                _sample(11, loss=1.05, latency_ms=101.0, throughput=1008.0, workers=(99.0, 102.0, 100.0, 101.0)),
                _sample(12, loss=1.18, latency_ms=102.0, throughput=1006.0, workers=(100.0, 103.0, 101.0, 102.0)),
                _sample(13, loss=1.25, latency_ms=101.0, throughput=1005.0, workers=(99.0, 101.0, 100.0, 102.0)),
            ),
        ),
        DemoPhase(
            name="BURST",
            samples=(
                _sample(20, loss=1.00, latency_ms=100.0, throughput=990.0, workers=(99.0, 102.0, 100.0, 103.0)),
                _sample(21, loss=1.00, latency_ms=102.0, throughput=988.0, workers=(100.0, 103.0, 101.0, 104.0)),
                _sample(22, loss=1.01, latency_ms=165.0, throughput=985.0, workers=(160.0, 166.0, 163.0, 167.0)),
                _sample(23, loss=1.00, latency_ms=101.0, throughput=989.0, workers=(99.0, 101.0, 100.0, 102.0)),
            ),
        ),
        DemoPhase(
            name="STRAGGLER",
            samples=(
                _sample(30, loss=1.00, latency_ms=100.0, throughput=980.0, workers=(98.0, 100.0, 101.0, 165.0)),
                _sample(31, loss=1.00, latency_ms=101.0, throughput=981.0, workers=(99.0, 101.0, 102.0, 170.0)),
                _sample(32, loss=1.01, latency_ms=99.0, throughput=979.0, workers=(97.0, 100.0, 99.0, 168.0)),
                _sample(33, loss=1.00, latency_ms=100.0, throughput=978.0, workers=(98.0, 101.0, 100.0, 172.0)),
            ),
        ),
        DemoPhase(
            name="RECOVER",
            samples=(
                _sample(40, loss=1.00, latency_ms=100.0, throughput=1000.0, workers=(98.0, 101.0, 99.0, 102.0)),
                _sample(41, loss=1.00, latency_ms=99.0, throughput=1001.0, workers=(97.0, 100.0, 98.0, 101.0)),
                _sample(42, loss=1.01, latency_ms=101.0, throughput=999.0, workers=(99.0, 102.0, 100.0, 103.0)),
                _sample(43, loss=1.00, latency_ms=100.0, throughput=1002.0, workers=(98.0, 101.0, 99.0, 102.0)),
            ),
        ),
        DemoPhase(
            name="NORMAL",
            samples=(
                _sample(50, loss=1.00, latency_ms=100.0, throughput=1015.0, workers=(98.0, 101.0, 99.0, 102.0)),
                _sample(51, loss=1.01, latency_ms=101.0, throughput=1016.0, workers=(99.0, 102.0, 100.0, 103.0)),
                _sample(52, loss=1.00, latency_ms=100.0, throughput=1017.0, workers=(98.0, 100.0, 99.0, 101.0)),
                _sample(53, loss=1.00, latency_ms=99.0, throughput=1015.0, workers=(97.0, 99.0, 98.0, 100.0)),
            ),
        ),
    ]


_CHORD_PRIORITY = {
    "stability_boost": 0,
    "latency_shed": 1,
    "straggler_relief": 2,
    "recover": 3,
    "recover_relock": 4,
}

_CHORD_LABELS = {
    "stability_boost": "DRIFT-RETUNE",
    "latency_shed": "BURST-ABSORB",
    "straggler_relief": "INPUT-STRAGGLER",
    "recover": "RECOVER",
    "recover_relock": "RELOCK",
}


def _select_chord(actions: list[Action]) -> str:
    if not actions:
        return "NORMAL-HOLD"

    names = {action.chord or action.reason or "normal_hold" for action in actions}
    chosen = sorted(names, key=lambda name: (_CHORD_PRIORITY.get(name, 99), name))[0]
    return _CHORD_LABELS.get(chosen, chosen.replace("_", "-").upper())


def _mode_from_phase(phase_name: str) -> str:
    if phase_name in {"DRIFT", "BURST", "STRAGGLER", "RECOVER"}:
        return phase_name
    return "NORMAL"


def _changed_knobs_from_actions(actions: list[Action]) -> list[str]:
    changed = sorted({action.knob for action in actions if isinstance(action.knob, str) and not action.knob.startswith("__")})
    return changed


def run_mk068_demo(out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)

    planner = ChordPlannerState(stable_intervals_required=99)
    timeline: list[dict] = []
    phases = _build_phases()

    for idx, phase in enumerate(phases):
        signals = analyze_signals(list(phase.samples))
        actions = propose_actions(signals, planner_state=planner)

        if any(action.reason == "recover" for action in actions):
            planner.mark_recovered()
        if any(action.reason == "relock" for action in actions):
            planner.mark_relocked()

        timeline.append(
            {
                "step_index": idx,
                "phase": phase.name,
                "mode": _mode_from_phase(phase.name),
                "chord": _select_chord(actions),
                "blocked_reason": "DEMO_PLAN_ONLY" if actions else None,
                "changed_knobs": _changed_knobs_from_actions(actions),
            }
        )

    artifact = {
        "schema_version": "mk068_demo.v0",
        "name": "mk068",
        "safe": True,
        "timeline": timeline,
    }
    artifact_path = out_dir / "mk068_demo_latest.json"
    artifact_path.write_text(json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return artifact_path
