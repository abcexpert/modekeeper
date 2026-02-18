from __future__ import annotations

from dataclasses import dataclass

from modekeeper.knobs import ActuatorRegistry
from modekeeper.chords.v1 import SAFE_CHORD_IDS_V1
from modekeeper.policy.actions import Action
from modekeeper.policy.chords import Chord
from modekeeper.policy.scalar import propose_scalar_actions

_DRIFT_RETUNE = SAFE_CHORD_IDS_V1[1]
_BURST_ABSORB = SAFE_CHORD_IDS_V1[2]
_INPUT_STRAGGLER = SAFE_CHORD_IDS_V1[3]
_RECOVER_RELOCK = SAFE_CHORD_IDS_V1[4]
_TIMEOUT_GUARD = "TIMEOUT-GUARD"


def _incident_from_signals(signals: dict) -> bool:
    if signals.get("incident") is True:
        return True
    return any(
        signals.get(key) is True
        for key in ("drift", "burst", "straggler", "gpu_saturated")
    )


@dataclass
class ChordPlannerState:
    stable_intervals_required: int = 2
    incident_seen: bool = False
    stable_intervals: int = 0
    recover_completed: bool = False

    def observe(self, signals: dict) -> None:
        incident = _incident_from_signals(signals)
        if incident:
            self.incident_seen = True
            self.stable_intervals = 0
            self.recover_completed = False
            return
        if self.incident_seen:
            self.stable_intervals += 1

    def relock_ready(self) -> bool:
        return (
            self.incident_seen
            and self.recover_completed
            and self.stable_intervals >= max(1, int(self.stable_intervals_required))
        )

    def mark_recovered(self) -> None:
        if self.incident_seen:
            self.recover_completed = True

    def mark_relocked(self) -> None:
        self.incident_seen = False
        self.stable_intervals = 0
        self.recover_completed = False


def _propose_chord_actions(
    signals: dict,
    planner_state: ChordPlannerState | None = None,
) -> list[Action]:
    actions: list[Action] = []
    gpu_saturated = signals.get("gpu_saturated") is True
    incident = _incident_from_signals(signals)

    if planner_state is not None:
        planner_state.observe(signals)
        # RECOVER is a dedicated step after incident clears.
        if planner_state.incident_seen and not incident and not planner_state.recover_completed:
            actions.extend(Chord(_RECOVER_RELOCK, [Action("__recover__", 0, "recover")]).to_actions())
            return actions
        # RELOCK can be suggested only after stabilization and RECOVER.
        if planner_state.relock_ready():
            actions.extend(
                Chord(_RECOVER_RELOCK, [Action("__relock__", 0, "relock")]).to_actions()
            )
            return actions

    if gpu_saturated:
        chord = Chord(
            _BURST_ABSORB,
            [
                Action("microbatch_size", 16, "gpu_saturated"),
            ],
        )
        actions.extend(chord.to_actions())

    if signals.get("drift"):
        stability_actions = [Action("grad_accum_steps", 8, "drift_detected")]
        # Если GPU saturated — microbatch уже уменьшаем выше и не раздуваем обратно до 32.
        if not gpu_saturated:
            stability_actions.append(Action("microbatch_size", 32, "drift_detected"))
        chord = Chord(
            _DRIFT_RETUNE,
            stability_actions,
        )
        actions.extend(chord.to_actions())

    if signals.get("burst"):
        chord = Chord(
            _BURST_ABSORB,
            [
                Action("dataloader_prefetch_factor", 2, "latency_burst"),
                Action("concurrency", 4, "latency_burst"),
            ],
        )
        actions.extend(chord.to_actions())

    if signals.get("straggler"):
        chord = Chord(_INPUT_STRAGGLER, [Action("dataloader_num_workers", 2, "straggler_detected")])
        actions.extend(chord.to_actions())
        actions.append(Action("timeout_ms", 15000, "straggler_detected", chord=_TIMEOUT_GUARD))

    return actions


def propose_actions(
    signals: dict,
    planner_state: ChordPlannerState | None = None,
    policy: str = "chord",
    registry: ActuatorRegistry | None = None,
) -> list[Action]:
    if policy == "chord":
        return _propose_chord_actions(signals, planner_state=planner_state)
    if policy == "scalar":
        if registry is None:
            raise ValueError("policy='scalar' requires registry")
        return propose_scalar_actions(signals, registry)
    raise ValueError(f"unknown policy: {policy!r} (expected 'chord' or 'scalar')")
