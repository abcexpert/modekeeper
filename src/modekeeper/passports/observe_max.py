from __future__ import annotations

from modekeeper.knobs import ActuatorRegistry
from modekeeper.core.analysis import analyze_signals
from modekeeper.core.summary import summarize_observe
from modekeeper.telemetry.models import TelemetrySample

_CANONICAL_ORDER = [
    "NORMAL-HOLD",
    "DRIFT-RETUNE",
    "BURST-ABSORB",
    "INPUT-STRAGGLER",
    "RECOVER",
    "RELOCK",
]


def _recommended_chords(signals: dict[str, object]) -> list[str]:
    selected = {"NORMAL-HOLD", "RECOVER", "RELOCK"}
    if signals.get("drift") is True:
        selected.add("DRIFT-RETUNE")
    if signals.get("burst") is True or signals.get("gpu_saturated") is True:
        selected.add("BURST-ABSORB")
    if signals.get("straggler") is True:
        selected.add("INPUT-STRAGGLER")
    return [chord for chord in _CANONICAL_ORDER if chord in selected]


def _best_effort_actuators(
    registry: ActuatorRegistry | None,
) -> tuple[list[str], list[str]]:
    if registry is None:
        return (["concurrency"], ["grad_accum_steps", "microbatch_size"])

    all_names = sorted(registry.list_names())
    if not all_names:
        return (["concurrency"], ["grad_accum_steps", "microbatch_size"])

    hot_candidates = {"concurrency", "dataloader_prefetch_factor"}
    hot = sorted(name for name in all_names if name in hot_candidates)
    cold = sorted(name for name in all_names if name not in hot_candidates)
    return hot, cold


def _knob_limits(registry: ActuatorRegistry | None) -> dict[str, dict[str, int]]:
    if registry is None:
        return {}
    limits: dict[str, dict[str, int]] = {}
    for name in sorted(registry.list_names()):
        knob = registry.get(name)
        if knob is None:
            continue
        limits[name] = {
            "min": int(knob.min_value),
            "max": int(knob.max_value),
        }
    return limits


def _redacted_proposals(allowed_chords: list[str]) -> list[dict[str, str]]:
    redacted: list[dict[str, str]] = []
    for index, _ in enumerate((ch for ch in allowed_chords if ch != "NORMAL-HOLD"), start=1):
        redacted.append({"proposal_id": f"P{index}"})
    return redacted


def build_observe_max_artifacts(
    samples: list[TelemetrySample],
    *,
    registry: ActuatorRegistry | None,
) -> tuple[dict[str, object], dict[str, object]]:
    signals = analyze_signals(samples)
    summary = summarize_observe(signals)
    allowed_chords = _recommended_chords(signals)
    hot, cold = _best_effort_actuators(registry)
    knob_limits = _knob_limits(registry)

    signal_flags = {
        "burst": bool(signals.get("burst") is True),
        "drift": bool(signals.get("drift") is True),
        "gpu_saturated": bool(signals.get("gpu_saturated") is True),
        "incident": bool(signals.get("incident") is True),
        "stable": bool(signals.get("stable") is True),
        "straggler": bool(signals.get("straggler") is True),
    }

    field_counts = {
        "gpu_mem_util_pct_non_null": 0,
        "gpu_util_pct_non_null": 0,
        "latency_ms_non_null": 0,
        "loss_non_null": 0,
        "worker_latencies_non_empty": 0,
    }
    for sample in samples:
        if getattr(sample, "gpu_mem_util_pct", None) is not None:
            field_counts["gpu_mem_util_pct_non_null"] += 1
        if getattr(sample, "gpu_util_pct", None) is not None:
            field_counts["gpu_util_pct_non_null"] += 1
        if getattr(sample, "latency_ms", None) is not None:
            field_counts["latency_ms_non_null"] += 1
        if getattr(sample, "loss", None) is not None:
            field_counts["loss_non_null"] += 1
        worker_latencies = getattr(sample, "worker_latencies_ms", None)
        if isinstance(worker_latencies, list) and worker_latencies:
            field_counts["worker_latencies_non_empty"] += 1

    active_flags = sorted(name for name, value in signal_flags.items() if value)
    summary_recommendations = summary.get("recommendations")
    if isinstance(summary_recommendations, list):
        recommendation_lines = [str(item) for item in summary_recommendations]
    else:
        recommendation_lines = []

    proposals = _redacted_proposals(allowed_chords)

    passport = {
        "schema_version": "passport.v0",
        "name": "observe_max",
        "description": "Free observation passport with best-effort coverage and propose-only recommendations.",
        "allowed_chords": allowed_chords,
        "allowed_actuators": {
            "hot": hot,
            "cold": cold,
        },
        "limits": {
            "cooldown_s": 60,
            "max_delta_per_step": 1,
            "relock_stable_intervals": 2,
            "knob_limits": knob_limits,
        },
        "invariants": [
            "propose_only",
            "no_apply",
            "redaction_required",
        ],
        "cooldowns": {},
        "gates": {
            "default_mode": "plan_verify_only",
            "apply": False,
            "propose_only": True,
            "require_verify_ok": True,
            "require_kill_switch_off": True,
        },
    }

    report = {
        "schema_version": "observe_max.v0",
        "name": "observe_max",
        "mode": "free_observe",
        "propose_only": True,
        "coverage": {
            "sample_count": len(samples),
            "signal_flags": signal_flags,
            "active_signal_flags": active_flags,
            "field_counts": field_counts,
            "observed_field_keys": sorted(field_counts.keys()),
        },
        "recommendation": {
            "proposals": proposals,
            "risk": str(summary.get("money_leak_risk", "unknown")),
            "top_symptoms": sorted(str(item) for item in summary.get("top_symptoms", [])),
            "recommendation_lines": recommendation_lines,
        },
        "redaction": {
            "enabled": True,
            "rules": [
                "no_paths",
                "no_k8s_identity",
                "no_raw_timestamps",
                "no_raw_observations",
            ],
        },
    }
    return passport, report
