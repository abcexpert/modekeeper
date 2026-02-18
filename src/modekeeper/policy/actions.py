from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Action:
    knob: str
    target: int
    reason: str
    chord: str | None = None

    def to_dict(self) -> dict:
        return {
            "knob": self.knob,
            "target": self.target,
            "reason": self.reason,
            "chord": self.chord,
        }
