from __future__ import annotations

from dataclasses import dataclass

from modekeeper.knobs import ActuatorRegistry
from modekeeper.policy.actions import Action
from modekeeper.safety.explain import ExplainLog


@dataclass
class RollbackResult:
    ok: bool
    error: str | None


def apply_with_rollback(
    registry: ActuatorRegistry,
    actions: list[Action],
    apply_fn,
    explain: ExplainLog,
) -> RollbackResult:
    snapshot = registry.snapshot()
    try:
        for action in actions:
            apply_fn(action)
    except Exception as exc:  # pragma: no cover - defensive
        registry.restore(snapshot)
        explain.emit(
            "rollback",
            {
                "reason": "exception",
                "error": str(exc),
                "snapshot": snapshot,
            },
        )
        return RollbackResult(ok=False, error=str(exc))
    return RollbackResult(ok=True, error=None)
