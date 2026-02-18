"""Chords v1 safe IDs."""

from __future__ import annotations

SAFE_CHORD_IDS_V1 = (
    "NORMAL-HOLD",
    "DRIFT-RETUNE",
    "BURST-ABSORB",
    "INPUT-STRAGGLER",
    "RECOVER-RELOCK",
)

_SAFE_CHORD_IDS_V1_SET = frozenset(SAFE_CHORD_IDS_V1)


def is_safe_chord_id(chord_id: str) -> bool:
    return chord_id in _SAFE_CHORD_IDS_V1_SET

