from __future__ import annotations

import time
from pathlib import Path

from modekeeper.safety.explain import ExplainLog

try:
    import pytorch_lightning as pl
except Exception:
    try:
        import lightning.pytorch as pl
    except Exception:
        pl = None

LIGHTNING_AVAILABLE = pl is not None


def build_lightning_callback(out_dir: Path) -> object | None:
    if pl is None:
        return None

    explain = ExplainLog(out_dir / "explain.jsonl")

    class ExplainCallback(pl.Callback):
        def __init__(self) -> None:
            super().__init__()
            self._fit_start = None
            self._batch_start = None

        def on_train_start(self, trainer, pl_module) -> None:
            now = time.monotonic()
            if self._fit_start is None:
                self._fit_start = now
            explain.emit("pl_train_start", {"t": now})

        def on_train_batch_start(self, trainer, pl_module, batch, batch_idx) -> None:
            now = time.monotonic()
            self._batch_start = now
            explain.emit("pl_train_batch_start", {"t": now, "batch_idx": batch_idx})

        def on_train_batch_end(self, trainer, pl_module, outputs, batch, batch_idx) -> None:
            now = time.monotonic()
            loss = _extract_loss(outputs)
            payload = {"t": now, "batch_idx": batch_idx, "loss": loss}
            if self._batch_start is not None:
                payload["batch_duration_s"] = now - self._batch_start
            explain.emit("pl_train_batch_end", payload)

        def on_fit_end(self, trainer, pl_module) -> None:
            now = time.monotonic()
            payload = {"t": now}
            if self._fit_start is not None:
                payload["fit_duration_s"] = now - self._fit_start
            explain.emit("pl_fit_end", payload)

    return ExplainCallback()


def _extract_loss(outputs: object) -> float | None:
    if outputs is None:
        return None
    if isinstance(outputs, (int, float)):
        return float(outputs)
    if isinstance(outputs, dict):
        if "loss" in outputs:
            return _extract_loss(outputs["loss"])
        return None
    if isinstance(outputs, (list, tuple)) and outputs:
        return _extract_loss(outputs[0])
    item = getattr(outputs, "item", None)
    if callable(item):
        try:
            return float(item())
        except Exception:
            return None
    return None
