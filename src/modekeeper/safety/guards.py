from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from modekeeper.knobs import ActuatorRegistry
from modekeeper.chords.catalog import load_default_catalog
from modekeeper.governance.approval import requires_approval
from modekeeper.policy.actions import Action
from modekeeper.safety.explain import ExplainLog


@dataclass
class ApplyResult:
    action: Action
    applied: bool
    blocked: bool
    reason: str
    dry_run: bool

    def to_dict(self) -> dict:
        return {
            "action": self.action.to_dict(),
            "applied": self.applied,
            "blocked": self.blocked,
            "reason": self.reason,
            "dry_run": self.dry_run,
        }


def split_actions_by_approval(
    actions: list[Action],
    *,
    apply_changes: bool,
    approve_advanced: bool,
    explain: ExplainLog | None = None,
) -> tuple[list[Action], dict[int, ApplyResult]]:
    catalog = load_default_catalog()
    chord_index = {
        item["id"]: item
        for item in catalog["chords"]
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }
    allowed_actions: list[Action] = []
    blocked_by_index: dict[int, ApplyResult] = {}
    for index, action in enumerate(actions):
        chord = action.chord.strip() if isinstance(action.chord, str) else ""
        if chord and chord not in chord_index:
            if explain is not None:
                explain.emit(
                    "blocked",
                    {"reason": "unknown_chord", "action": action.to_dict()},
                )
            blocked_by_index[index] = ApplyResult(
                action=action,
                applied=False,
                blocked=True,
                reason="unknown_chord",
                dry_run=True,
            )
            continue

        chord_is_advanced = chord and chord_index.get(chord, {}).get("risk_tier") == "advanced"
        needs_advanced_approval = bool(chord_is_advanced) or requires_approval(action)
        if apply_changes and (not approve_advanced) and needs_advanced_approval:
            if explain is not None:
                explain.emit(
                    "blocked",
                    {"reason": "approval_required", "action": action.to_dict()},
                )
            blocked_by_index[index] = ApplyResult(
                action=action,
                applied=False,
                blocked=True,
                reason="approval_required",
                dry_run=True,
            )
            continue
        allowed_actions.append(action)
    return allowed_actions, blocked_by_index


class Guardrails:
    def __init__(
        self,
        registry: ActuatorRegistry,
        explain: ExplainLog,
        allowlist: list[str] | None = None,
        min_interval_s: int = 30,
        max_delta_per_step: int = 0,
        relock_stable_intervals: int = 2,
    ) -> None:
        self.registry = registry
        self.explain = explain
        registry_names = set(registry.list_names())
        if allowlist is None:
            self.allowlist = registry_names
        else:
            self.allowlist = set(allowlist) & registry_names
        self.min_interval = timedelta(seconds=max(0, int(min_interval_s)))
        self.max_delta_per_step = max(0, int(max_delta_per_step))
        self.relock_stable_intervals = max(1, int(relock_stable_intervals))
        self.last_stable_profile: dict[str, int] | None = None
        self.last_stable_at: datetime | None = None
        self._stable_without_incident = 0
        self._recover_completed = False

    def _emit_explain_best_effort(self, event: str, payload: dict) -> None:
        explain = getattr(self, "explain", None)
        if explain is None:
            return
        emit = getattr(explain, "emit", None)
        if not callable(emit):
            return
        try:
            emit(event, payload)
        except Exception:
            return

    def _allowlisted_snapshot(self) -> dict[str, int]:
        snapshot: dict[str, int] = {}
        for name in sorted(self.allowlist):
            knob = self.registry.get(name)
            if knob is None:
                continue
            snapshot[name] = knob.value
        return snapshot

    def mark_stable_profile(self, reason: str = "stable") -> dict[str, int]:
        profile = self._allowlisted_snapshot()
        self.last_stable_profile = profile
        self.last_stable_at = datetime.now(timezone.utc)
        self._emit_explain_best_effort(
            "stable_profile_saved",
            {
                "reason": reason,
                "profile": profile,
                "stable_at": self.last_stable_at.isoformat(),
            },
        )
        return profile

    def rollback_to_last_stable(self, reason: str, apply_changes: bool) -> list[ApplyResult]:
        if self.last_stable_profile is None:
            self._emit_explain_best_effort(
                "rollback",
                {
                    "reason": reason,
                    "before": {},
                    "after": {},
                    "changed": [],
                },
            )
            return []

        changed: list[str] = []
        before: dict[str, int] = {}
        after: dict[str, int] = {}
        actions: list[Action] = []
        for name in sorted(self.last_stable_profile.keys()):
            knob = self.registry.get(name)
            if knob is None:
                continue
            target = self.last_stable_profile[name]
            if knob.value == target:
                continue
            changed.append(name)
            before[name] = knob.value
            actions.append(Action(name, target, reason="rollback"))

        if apply_changes:
            for action in actions:
                knob = self.registry.get(action.knob)
                if knob is None:
                    continue
                after[action.knob] = knob.apply(action.target)
        else:
            for action in actions:
                after[action.knob] = action.target

        self._emit_explain_best_effort(
            "rollback",
            {
                "reason": reason,
                "before": before,
                "after": after,
                "changed": changed,
            },
        )

        results: list[ApplyResult] = []
        for action in actions:
            if apply_changes:
                results.append(
                    ApplyResult(
                        action=action,
                        applied=True,
                        blocked=False,
                        reason="rollback",
                        dry_run=False,
                    )
                )
            else:
                results.append(
                    ApplyResult(
                        action=action,
                        applied=False,
                        blocked=False,
                        reason="rollback_dry_run",
                        dry_run=True,
                    )
                )
        return results

    def _kill_switch_active(self) -> bool:
        return os.environ.get("MODEKEEPER_KILL_SWITCH", "").strip() == "1"

    def _incident_from_signals(self, signals: dict) -> bool:
        if signals.get("incident") is True:
            return True
        return any(
            signals.get(key) is True
            for key in ("drift", "burst", "straggler", "gpu_saturated")
        )

    def observe_signals(self, signals: dict) -> None:
        if self._incident_from_signals(signals):
            self._stable_without_incident = 0
            self._recover_completed = False
            return
        self._stable_without_incident += 1

    def _relock_allowed(self) -> bool:
        return (
            self._recover_completed
            and self.last_stable_profile is not None
            and self._stable_without_incident >= self.relock_stable_intervals
        )

    def _check_allowed(self, action: Action) -> tuple[bool, str, dict | None]:
        knob = self.registry.get(action.knob)
        if knob is None:
            return False, "unknown_knob", None
        if action.knob not in self.allowlist:
            return False, "not_allowlisted", None
        last = knob.last_changed_at
        if last is not None:
            now = datetime.now(timezone.utc)
            if last.tzinfo is None:
                last = last.replace(tzinfo=timezone.utc)
            else:
                last = last.astimezone(timezone.utc)
            if now - last < self.min_interval:
                return False, "cooldown_active", None
        if self.max_delta_per_step > 0:
            current = knob.value
            clamped_target = knob.clamp(action.target)
            delta = abs(clamped_target - current)
            if delta > self.max_delta_per_step:
                return (
                    False,
                    "max_delta_exceeded",
                    {
                        "current": current,
                        "target": action.target,
                        "clamped_target": clamped_target,
                        "delta": delta,
                        "max_delta_per_step": self.max_delta_per_step,
                    },
                )
        return True, "ok", None

    def evaluate_and_apply(
        self,
        actions: list[Action],
        apply_changes: bool,
        entitlement_apply_enabled: bool | None = None,
    ) -> list[ApplyResult]:
        results: list[ApplyResult] = []

        if self._kill_switch_active():
            for action in actions:
                self.explain.emit(
                    "blocked",
                    {"reason": "kill_switch", "action": action.to_dict()},
                )
                results.append(
                    ApplyResult(
                        action=action,
                        applied=False,
                        blocked=True,
                        reason="kill_switch",
                        dry_run=True,
                    )
                )
            return results

        if apply_changes and entitlement_apply_enabled is False:
            for action in actions:
                self.explain.emit(
                    "blocked",
                    {"reason": "entitlement_missing", "action": action.to_dict()},
                )
                results.append(
                    ApplyResult(
                        action=action,
                        applied=False,
                        blocked=True,
                        reason="entitlement_missing",
                        dry_run=True,
                    )
                )
            return results

        allowed_actions: list[Action] = []
        for action in actions:
            if action.reason == "recover":
                self._recover_completed = True
                self.explain.emit(
                    "decision",
                    {"reason": "recover_completed", "action": action.to_dict()},
                )
                results.append(
                    ApplyResult(
                        action=action,
                        applied=apply_changes,
                        blocked=False,
                        reason="recover",
                        dry_run=not apply_changes,
                    )
                )
                continue

            if action.reason == "relock":
                if not self._relock_allowed():
                    self.explain.emit(
                        "blocked",
                        {
                            "reason": "relock_not_allowed",
                            "action": action.to_dict(),
                            "recover_completed": self._recover_completed,
                            "stable_without_incident": self._stable_without_incident,
                            "stable_required": self.relock_stable_intervals,
                            "has_stable_profile": self.last_stable_profile is not None,
                        },
                    )
                    results.append(
                        ApplyResult(
                            action=action,
                            applied=False,
                            blocked=True,
                            reason="relock_not_allowed",
                            dry_run=True,
                        )
                    )
                    continue
                self.explain.emit(
                    "decision",
                    {"reason": "relock_allowed", "action": action.to_dict()},
                )
                rollback_results = self.rollback_to_last_stable(
                    reason="relock",
                    apply_changes=apply_changes,
                )
                if rollback_results:
                    results.extend(rollback_results)
                else:
                    results.append(
                        ApplyResult(
                            action=action,
                            applied=apply_changes,
                            blocked=False,
                            reason="relock_noop" if apply_changes else "relock_dry_run_noop",
                            dry_run=not apply_changes,
                        )
                    )
                continue

            if action.reason == "normal":
                if not self._recover_completed:
                    self.explain.emit(
                        "blocked",
                        {"reason": "normal_requires_recover", "action": action.to_dict()},
                    )
                    results.append(
                        ApplyResult(
                            action=action,
                            applied=False,
                            blocked=True,
                            reason="normal_requires_recover",
                            dry_run=True,
                        )
                    )
                    continue
                self.explain.emit(
                    "decision",
                    {"reason": "normal_allowed", "action": action.to_dict()},
                )
                results.append(
                    ApplyResult(
                        action=action,
                        applied=apply_changes,
                        blocked=False,
                        reason="normal_allowed",
                        dry_run=not apply_changes,
                    )
                )
                continue

            allowed, reason, payload_extra = self._check_allowed(action)
            if not allowed:
                payload = {"reason": reason, "action": action.to_dict()}
                if payload_extra:
                    payload.update(payload_extra)
                self.explain.emit(
                    "blocked",
                    payload,
                )
                results.append(
                    ApplyResult(
                        action=action,
                        applied=False,
                        blocked=True,
                        reason=reason,
                        dry_run=True,
                    )
                )
            else:
                allowed_actions.append(action)

        if not apply_changes:
            for action in allowed_actions:
                self.explain.emit(
                    "dry_run",
                    {"reason": "apply_gate", "action": action.to_dict()},
                )
                results.append(
                    ApplyResult(
                        action=action,
                        applied=False,
                        blocked=False,
                        reason="dry_run",
                        dry_run=True,
                    )
                )
            return results

        for action in allowed_actions:
            knob = self.registry.get(action.knob)
            if knob is None:
                self.explain.emit(
                    "blocked",
                    {"reason": "unknown_knob", "action": action.to_dict()},
                )
                results.append(
                    ApplyResult(
                        action=action,
                        applied=False,
                        blocked=True,
                        reason="unknown_knob",
                        dry_run=True,
                    )
                )
                continue
            before = knob.value
            after = knob.apply(action.target)
            self.explain.emit(
                "applied",
                {"action": action.to_dict(), "before": before, "after": after},
            )
            results.append(
                ApplyResult(
                    action=action,
                    applied=True,
                    blocked=False,
                    reason="applied",
                    dry_run=False,
                )
            )

        return results
