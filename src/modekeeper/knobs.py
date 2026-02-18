from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass
class Knob:
    name: str
    min_value: int
    max_value: int
    step: int
    value: int
    last_changed_at: datetime | None = None

    def clamp(self, target: int) -> int:
        if target < self.min_value:
            return self.min_value
        if target > self.max_value:
            return self.max_value
        return target

    def apply(self, target: int) -> int:
        target = self.clamp(target)
        self.value = target
        self.last_changed_at = datetime.now(timezone.utc)
        return self.value


class ActuatorRegistry:
    def __init__(self) -> None:
        self._knobs: dict[str, Knob] = {}

    def register(self, knob: Knob) -> None:
        self._knobs[knob.name] = knob

    def get(self, name: str) -> Knob | None:
        return self._knobs.get(name)

    def snapshot(self) -> dict[str, int]:
        return {k: v.value for k, v in self._knobs.items()}

    def restore(self, snapshot: dict[str, int]) -> None:
        for name, value in snapshot.items():
            if name in self._knobs:
                self._knobs[name].value = value

    def list_names(self) -> list[str]:
        return list(self._knobs.keys())
