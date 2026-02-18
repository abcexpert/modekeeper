import json
from pathlib import Path

from modekeeper.knobs import ActuatorRegistry, Knob
from modekeeper.policy.actions import Action
from modekeeper.policy.rules import ChordPlannerState, propose_actions
from modekeeper.safety.explain import ExplainLog
from modekeeper.safety.guards import Guardrails


def _read_events(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _registry() -> ActuatorRegistry:
    registry = ActuatorRegistry()
    registry.register(Knob("concurrency", 1, 16, step=1, value=4))
    registry.register(Knob("dataloader_prefetch_factor", 1, 8, step=1, value=2))
    return registry


def test_relock_not_proposed_and_blocked_without_stabilization(tmp_path: Path) -> None:
    planner = ChordPlannerState(stable_intervals_required=2)
    proposed = propose_actions({"incident": True, "drift": True}, planner_state=planner)
    assert not any(action.reason == "relock" for action in proposed)

    explain = ExplainLog(tmp_path / "explain.jsonl")
    guardrails = Guardrails(registry=_registry(), explain=explain, relock_stable_intervals=2)
    guardrails.mark_stable_profile()
    guardrails.observe_signals({"incident": True})
    blocked = guardrails.evaluate_and_apply([Action("__relock__", 0, "relock")], apply_changes=True)
    assert blocked[0].blocked is True
    assert blocked[0].reason == "relock_not_allowed"


def test_relock_proposed_and_allowed_only_after_stabilization(tmp_path: Path) -> None:
    planner = ChordPlannerState(stable_intervals_required=2)
    propose_actions({"incident": True, "burst": True}, planner_state=planner)

    recover_actions = propose_actions(
        {"incident": False, "stable": True},
        planner_state=planner,
    )
    assert [a.reason for a in recover_actions] == ["recover"]

    planner.mark_recovered()
    relock_actions = propose_actions(
        {"incident": False, "stable": True},
        planner_state=planner,
    )
    assert [a.reason for a in relock_actions] == ["relock"]

    explain = ExplainLog(tmp_path / "explain.jsonl")
    registry = _registry()
    guardrails = Guardrails(registry=registry, explain=explain, relock_stable_intervals=2)
    guardrails.mark_stable_profile()
    concurrency = registry.get("concurrency")
    assert concurrency is not None
    concurrency.apply(2)

    guardrails.observe_signals({"incident": True})
    guardrails.observe_signals({"incident": False, "stable": True})
    guardrails.evaluate_and_apply([Action("__recover__", 0, "recover")], apply_changes=True)
    guardrails.observe_signals({"incident": False, "stable": True})

    relock = guardrails.evaluate_and_apply([Action("__relock__", 0, "relock")], apply_changes=True)
    assert relock
    assert all(item.blocked is False for item in relock)
    assert concurrency.value == 4


def test_transition_to_normal_requires_recover(tmp_path: Path) -> None:
    explain = ExplainLog(tmp_path / "explain.jsonl")
    guardrails = Guardrails(registry=_registry(), explain=explain, relock_stable_intervals=2)

    blocked = guardrails.evaluate_and_apply([Action("__normal__", 0, "normal")], apply_changes=True)
    assert blocked[0].blocked is True
    assert blocked[0].reason == "normal_requires_recover"

    guardrails.evaluate_and_apply([Action("__recover__", 0, "recover")], apply_changes=False)
    allowed = guardrails.evaluate_and_apply([Action("__normal__", 0, "normal")], apply_changes=True)
    assert allowed[0].blocked is False
    assert allowed[0].reason == "normal_allowed"


def test_relock_block_writes_explain_reason(tmp_path: Path) -> None:
    explain_path = tmp_path / "explain.jsonl"
    explain = ExplainLog(explain_path)
    guardrails = Guardrails(registry=_registry(), explain=explain, relock_stable_intervals=2)
    guardrails.mark_stable_profile()
    guardrails.observe_signals({"incident": False, "stable": True})

    guardrails.evaluate_and_apply([Action("__relock__", 0, "relock")], apply_changes=True)

    blocked = [event for event in _read_events(explain_path) if event.get("event") == "blocked"]
    assert blocked
    payload = blocked[-1].get("payload", {})
    assert payload.get("reason") == "relock_not_allowed"
