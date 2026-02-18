from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import TextIO


def _short_error(err: Exception) -> str:
    text = str(err).strip()
    if not text:
        text = err.__class__.__name__
    if len(text) > 200:
        text = text[:197] + "..."
    return text


@dataclass
class RawRecorder:
    path: Path | None
    mode: str = "w"
    lines_written: int = 0
    error: str | None = None
    _fh: TextIO | None = None

    def __post_init__(self) -> None:
        if self.path is None:
            return
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._fh = self.path.open(self.mode, encoding="utf-8")
        except Exception as e:
            self.error = _short_error(e)
            self._fh = None

    def write_line(self, line: str) -> None:
        if self._fh is None or self.error is not None:
            return
        try:
            self._fh.write(line)
            self.lines_written += 1
        except Exception as e:
            self.error = _short_error(e)
            try:
                self._fh.close()
            except Exception:
                pass
            self._fh = None

    def close(self) -> None:
        if self._fh is None:
            return
        try:
            self._fh.close()
        except Exception as e:
            if self.error is None:
                self.error = _short_error(e)
        self._fh = None
