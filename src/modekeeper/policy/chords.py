from __future__ import annotations

from dataclasses import dataclass

from modekeeper.policy.actions import Action


@dataclass
class Chord:
    name: str
    actions: list[Action]

    def to_actions(self) -> list[Action]:
        for action in self.actions:
            action.chord = self.name
        return self.actions
