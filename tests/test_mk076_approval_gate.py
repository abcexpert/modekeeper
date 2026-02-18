from modekeeper.policy.actions import Action
from modekeeper.safety.guards import split_actions_by_approval


def test_advanced_action_requires_approval_when_applying() -> None:
    actions = [
        Action("timeout_ms", 15000, "straggler_detected", chord="TIMEOUT-GUARD"),
        Action("dataloader_num_workers", 2, "straggler_detected", chord="INPUT-STRAGGLER"),
    ]

    allowed, blocked = split_actions_by_approval(
        actions,
        apply_changes=True,
        approve_advanced=False,
    )

    assert len(allowed) == 1
    assert allowed[0].knob == "dataloader_num_workers"
    assert 0 in blocked
    assert blocked[0].dry_run is True
    assert blocked[0].reason == "approval_required"
    assert blocked[0].applied is False


def test_advanced_action_applies_when_approved() -> None:
    actions = [
        Action("timeout_ms", 15000, "straggler_detected", chord="TIMEOUT-GUARD"),
        Action("dataloader_num_workers", 2, "straggler_detected", chord="INPUT-STRAGGLER"),
    ]

    allowed, blocked = split_actions_by_approval(
        actions,
        apply_changes=True,
        approve_advanced=True,
    )

    assert len(allowed) == 2
    assert blocked == {}

