from __future__ import annotations

from enum import Enum

import pytest

from modekeeper.core.modes import Mode
from modekeeper.core.state_machine import ModeStateMachine


class FakeMode(Enum):
    OTHER = "OTHER"


def test_state_machine_transitions() -> None:
    sm = ModeStateMachine(Mode.OBSERVE_ONLY)
    sm.transition(Mode.CLOSED_LOOP)
    assert sm.mode == Mode.CLOSED_LOOP
    sm.transition(Mode.OBSERVE_ONLY)
    assert sm.mode == Mode.OBSERVE_ONLY


def test_state_machine_invalid_transition() -> None:
    sm = ModeStateMachine(Mode.OBSERVE_ONLY)
    with pytest.raises(ValueError):
        sm.transition(FakeMode.OTHER)  # type: ignore[arg-type]
