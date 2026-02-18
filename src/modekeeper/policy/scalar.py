from __future__ import annotations

from modekeeper.knobs import ActuatorRegistry
from modekeeper.policy.actions import Action


def scalar_action(signals: dict) -> float:
    level = 0.0
    if signals.get("stable") is True:
        level = max(level, 0.0)
    if signals.get("incident") is True:
        level = max(level, 0.5)
    if signals.get("drift") is True:
        level = max(level, 0.5)
    if signals.get("burst") is True:
        level = max(level, 0.75)
    if signals.get("straggler") is True:
        level = max(level, 1.0)
    if signals.get("gpu_saturated") is True:
        level = max(level, 1.0)
    return min(1.0, max(0.0, level))


def propose_scalar_actions(signals: dict, registry: ActuatorRegistry) -> list[Action]:
    knob = registry.get("concurrency")
    if knob is None:
        return []

    u = scalar_action(signals)
    if u <= 0.0:
        return []

    step_mult = max(1, int(round(u * 4)))
    target = knob.clamp(knob.value - (step_mult * knob.step))
    if target == knob.value:
        return []

    return [Action("concurrency", target, reason="scalar", chord="SCALAR")]
