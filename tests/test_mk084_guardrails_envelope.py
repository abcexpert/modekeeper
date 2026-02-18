from modekeeper.policy.actions import Action
from modekeeper.safety.guards import split_actions_by_approval


def test_mk084_unknown_chord_is_blocked() -> None:
    actions = [Action("dataloader_num_workers", 2, "test", chord="NO-SUCH-CHORD")]

    allowed, blocked = split_actions_by_approval(
        actions,
        apply_changes=True,
        approve_advanced=True,
    )

    assert allowed == []
    assert 0 in blocked
    assert blocked[0].reason == "unknown_chord"


def test_mk084_advanced_chord_requires_approval() -> None:
    actions = [Action("dataloader_num_workers", 2, "test", chord="COMM-CONGESTION")]

    allowed_blocked, blocked = split_actions_by_approval(
        actions,
        apply_changes=True,
        approve_advanced=False,
    )
    assert allowed_blocked == []
    assert 0 in blocked
    assert blocked[0].reason == "approval_required"

    allowed_approved, blocked_approved = split_actions_by_approval(
        actions,
        apply_changes=True,
        approve_advanced=True,
    )
    assert len(allowed_approved) == 1
    assert blocked_approved == {}
