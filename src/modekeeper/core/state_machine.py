from __future__ import annotations

from dataclasses import dataclass

from modekeeper.core.modes import Mode


@dataclass
class ModeStateMachine:
    mode: Mode

    def transition(self, target: Mode) -> None:
        if self.mode == target:
            return
        if self.mode == Mode.OBSERVE_ONLY and target == Mode.CLOSED_LOOP:
            self.mode = target
            return
        if self.mode == Mode.CLOSED_LOOP and target == Mode.OBSERVE_ONLY:
            self.mode = target
            return
        raise ValueError(f"Invalid transition: {self.mode} -> {target}")
