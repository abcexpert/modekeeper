from __future__ import annotations

from enum import Enum


class Mode(str, Enum):
    OBSERVE_ONLY = "OBSERVE_ONLY"
    CLOSED_LOOP = "CLOSED_LOOP"
