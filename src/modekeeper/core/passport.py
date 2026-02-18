from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from modekeeper.core.modes import Mode


@dataclass
class ModePassport:
    mode: Mode
    started_at: datetime
    expires_at: datetime | None

    @classmethod
    def observe_only_week(cls) -> "ModePassport":
        now = datetime.utcnow()
        return cls(mode=Mode.OBSERVE_ONLY, started_at=now, expires_at=now + timedelta(days=7))

    @classmethod
    def closed_loop(cls) -> "ModePassport":
        return cls(mode=Mode.CLOSED_LOOP, started_at=datetime.utcnow(), expires_at=None)
