from __future__ import annotations

from modekeeper.core.analysis import analyze_signals
from modekeeper.policy.actions import Action
from modekeeper.policy.rules import ChordPlannerState, propose_actions
from modekeeper.telemetry.models import TelemetrySample

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


def _changed_knobs(actions: list[Action]) -> list[str]:
    return sorted(
        {
            action.knob
            for action in actions
            if isinstance(action.knob, str) and not action.knob.startswith("__")
        }
    )


def _select_chord(actions: list[Action]) -> str:
    if not actions:
        return "NORMAL-HOLD"
    names = {action.chord or action.reason or "normal_hold" for action in actions}
    chosen = sorted(names, key=lambda name: (_CHORD_PRIORITY.get(name, 99), name))[0]
    return _CHORD_LABELS.get(chosen, chosen.replace("_", "-").upper())


def _mode_from_step(signals: dict, actions: list[Action]) -> str:
    if signals.get("drift") is True:
        return "DRIFT"
    if signals.get("burst") is True:
        return "BURST"
    if signals.get("straggler") is True:
        return "STRAGGLER"
    if any(action.reason in {"recover", "relock"} for action in actions):
        return "RECOVER"
    return "NORMAL"


def _to_scalar_baseline(actions: list[Action]) -> list[Action]:
    filtered = [
        action
        for action in actions
        if isinstance(action.knob, str) and not action.knob.startswith("__")
    ]
    if not filtered:
        return []
    filtered.sort(
        key=lambda action: (
            action.knob,
            action.reason or "",
            action.chord or "",
        )
    )
    return [filtered[0]]


def _build_summary(*, timeline: list[dict], baseline: bool) -> dict:
    distinct_knobs = sorted(
        {
            knob
            for step in timeline
            for knob in step.get("changed_knobs", [])
            if isinstance(knob, str)
        }
    )
    steps_with_changes = sum(1 for step in timeline if step.get("changed_knobs"))
    knob_changes_total = sum(len(step.get("changed_knobs", [])) for step in timeline)
    estimated_apply_steps = knob_changes_total if baseline else steps_with_changes
    return {
        "ticks_total": len(timeline),
        "steps_with_changes": steps_with_changes,
        "knob_changes_total": knob_changes_total,
        "distinct_knobs_changed": distinct_knobs,
        "estimated_apply_steps": estimated_apply_steps,
    }


def _run_replay(
    *,
    samples: list[TelemetrySample],
    baseline: bool,
) -> dict:
    planner = ChordPlannerState(stable_intervals_required=2)
    timeline: list[dict] = []
    for tick in range(len(samples)):
        window = samples[max(0, tick - 3) : tick + 1]
        signals = analyze_signals(window)
        actions = propose_actions(signals, planner_state=planner)
        if baseline:
            actions = _to_scalar_baseline(actions)

        if any(action.reason == "recover" for action in actions):
            planner.mark_recovered()
        if any(action.reason == "relock" for action in actions):
            planner.mark_relocked()

        timeline.append(
            {
                "tick": tick,
                "mode": _mode_from_step(signals, actions),
                "chord": _select_chord(actions),
                "blocked_reason": "PLAN_ONLY" if actions else None,
                "changed_knobs": _changed_knobs(actions),
            }
        )
    summary = _build_summary(timeline=timeline, baseline=baseline)
    return {"timeline": timeline, "summary": summary}


def build_mk074_before_after(
    *,
    samples: list[TelemetrySample],
    observe_source: str,
    observe_path: str | None,
) -> tuple[dict, dict, dict]:
    before_data = _run_replay(samples=samples, baseline=True)
    after_data = _run_replay(samples=samples, baseline=False)

    before = {
        "schema_version": "mk074_before.v0",
        "policy": "scalar_baseline",
        "safe": True,
        **before_data,
    }
    after = {
        "schema_version": "mk074_after.v0",
        "policy": "chord",
        "safe": True,
        **after_data,
    }

    before_steps = int(before["summary"]["estimated_apply_steps"])
    after_steps = int(after["summary"]["estimated_apply_steps"])
    diff = {
        "estimated_apply_steps_saved": max(0, before_steps - after_steps),
        "steps_with_changes_delta": int(before["summary"]["steps_with_changes"])
        - int(after["summary"]["steps_with_changes"]),
        "knob_changes_total_delta": int(before["summary"]["knob_changes_total"])
        - int(after["summary"]["knob_changes_total"]),
    }
    combined = {
        "schema_version": "mk074_before_after.v0",
        "replay_info": {"observe_source": observe_source, "observe_path": observe_path},
        "before": before,
        "after": after,
        "diff": diff,
    }
    return before, after, combined

