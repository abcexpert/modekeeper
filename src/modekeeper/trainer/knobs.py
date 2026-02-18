"""Helpers for reading knob annotations from Downward API files."""

from __future__ import annotations

import ast


def parse_downward_annotations(text: str, prefix: str = "modekeeper/knob.") -> dict[str, str]:
    """Parse a Downward API annotations file into a knob map.

    Expected line format is: key="value". Only keys that start with ``prefix`` are returned.
    Returned keys have the prefix stripped.
    """

    knobs: dict[str, str] = {}
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or "=" not in line:
            continue
        key, raw_value = line.split("=", 1)
        key = key.strip()
        raw_value = raw_value.strip()
        if not key.startswith(prefix):
            continue
        if not raw_value.startswith('"') or not raw_value.endswith('"'):
            continue
        try:
            value = ast.literal_eval(raw_value)
        except (ValueError, SyntaxError):
            continue
        if not isinstance(value, str):
            continue
        knob_key = key[len(prefix) :]
        if knob_key:
            knobs[knob_key] = value
    return knobs
