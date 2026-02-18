from modekeeper.knobs import ActuatorRegistry, Knob
from modekeeper.policy.scalar import propose_scalar_actions, scalar_action


def _registry() -> ActuatorRegistry:
    registry = ActuatorRegistry()
    registry.register(Knob("concurrency", 1, 64, step=1, value=8))
    return registry


def test_scalar_action_is_deterministic_and_in_range() -> None:
    cases = [
        {"stable": True},
        {"drift": True},
        {"burst": True},
        {"straggler": True},
        {"drift": True, "burst": True},
        {"drift": True, "straggler": True},
    ]
    for signals in cases:
        first = scalar_action(signals)
        second = scalar_action(signals)
        assert first == second
        assert 0.0 <= first <= 1.0


def test_scalar_action_uses_max_logic() -> None:
    assert scalar_action({"stable": True}) == 0.0
    assert scalar_action({"drift": True}) == 0.5
    assert scalar_action({"burst": True}) == 0.75
    assert scalar_action({"straggler": True}) == 1.0
    assert scalar_action({"drift": True, "burst": True}) == 0.75
    assert scalar_action({"burst": True, "straggler": True}) == 1.0


def test_propose_scalar_actions_stable_and_incident() -> None:
    registry = _registry()
    stable_actions = propose_scalar_actions({"stable": True, "incident": False}, registry)
    assert stable_actions == []

    incident = {"incident": True, "burst": True}
    first = propose_scalar_actions(incident, registry)
    second = propose_scalar_actions(incident, registry)
    assert first == second
    assert len(first) >= 1
    assert first[0].knob == "concurrency"
    assert first[0].reason == "scalar"
    assert first[0].chord == "SCALAR"
