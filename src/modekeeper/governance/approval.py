from __future__ import annotations

from modekeeper.policy.actions import Action

ADVANCED_ACTUATORS = {
    "timeout_ms",
    "comm_bucket_mb",
}

ADVANCED_CHORD_IDS = {
    "TIMEOUT-GUARD",
    "COMM-CONGESTION",
    "NEAR-HANG/TIMEOUT-GUARD",
}


def requires_approval(action: Action) -> bool:
    return action.knob in ADVANCED_ACTUATORS or action.chord in ADVANCED_CHORD_IDS

