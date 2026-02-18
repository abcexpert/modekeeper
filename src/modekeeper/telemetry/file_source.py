from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from modekeeper.telemetry.models import TelemetrySample
from modekeeper.telemetry.raw_recorder import RawRecorder
from modekeeper.telemetry.sources import TelemetrySource

_NUMERIC_TS_RE = re.compile(r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)$")


@dataclass
class ObserveIngestStats:
    dropped_invalid_json: int = 0
    dropped_invalid_shape: int = 0
    dropped_missing_fields: int = 0

    @property
    def dropped_total(self) -> int:
        return (
            self.dropped_invalid_json
            + self.dropped_invalid_shape
            + self.dropped_missing_fields
        )

    def to_dict(self) -> dict[str, int]:
        return {
            "dropped_total": self.dropped_total,
            "dropped_invalid_json": self.dropped_invalid_json,
            "dropped_invalid_shape": self.dropped_invalid_shape,
            "dropped_missing_fields": self.dropped_missing_fields,
        }


def _zero_ingest_stats() -> dict[str, int]:
    return ObserveIngestStats().to_dict()


@dataclass
class FileSource(TelemetrySource):
    path: Path
    record_raw_path: Path | None = None
    record_raw_mode: str = "w"
    rows_read: int = 0
    observe_ingest: dict[str, int] = field(default_factory=_zero_ingest_stats)
    record_raw_lines_written: int = 0
    record_raw_error: str | None = None

    def read(self) -> list[TelemetrySample]:
        suffix = self.path.suffix.lower()
        if suffix == ".jsonl":
            samples = self._read_jsonl()
        elif suffix == ".csv":
            samples = self._read_csv()
        else:
            raise ValueError(f"Unsupported file type: {self.path}")
        return samples

    def _read_jsonl(self) -> list[TelemetrySample]:
        samples: list[TelemetrySample] = []
        stats = ObserveIngestStats()
        rows_read = 0
        recorder = RawRecorder(self.record_raw_path, mode=self.record_raw_mode)
        try:
            with self.path.open("r", encoding="utf-8") as f:
                for line in f:
                    rows_read += 1
                    recorder.write_line(line)
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        record = json.loads(line)
                    except Exception:
                        stats.dropped_invalid_json += 1
                        continue
                    if not isinstance(record, dict):
                        stats.dropped_invalid_shape += 1
                        continue
                    try:
                        sample = _record_to_sample(record)
                    except ValueError:
                        stats.dropped_missing_fields += 1
                        continue
                    samples.append(sample)
        finally:
            recorder.close()
        self.rows_read = rows_read
        self.observe_ingest = stats.to_dict()
        self.record_raw_lines_written = recorder.lines_written
        self.record_raw_error = recorder.error
        return samples

    def _read_csv(self) -> list[TelemetrySample]:
        samples: list[TelemetrySample] = []
        stats = ObserveIngestStats()
        rows_read = 0
        recorder = RawRecorder(self.record_raw_path, mode=self.record_raw_mode)
        try:
            with self.path.open("r", encoding="utf-8", newline="") as f:
                raw_text = f.read()
            for line in raw_text.splitlines(keepends=True):
                recorder.write_line(line)
            reader = csv.DictReader(raw_text.splitlines())
            for row in reader:
                rows_read += 1
                try:
                    sample = _record_to_sample(row)
                except ValueError:
                    stats.dropped_missing_fields += 1
                    continue
                samples.append(sample)
        finally:
            recorder.close()
        self.rows_read = rows_read
        self.observe_ingest = stats.to_dict()
        self.record_raw_lines_written = recorder.lines_written
        self.record_raw_error = recorder.error
        return samples


def _record_to_sample(record: dict) -> TelemetrySample:
    ts = record.get("ts")
    if ts is None:
        raise ValueError("Missing ts field")
    timestamp_ms = _parse_ts_ms(str(ts))

    step_time_ms = record.get("step_time_ms")
    if step_time_ms is None:
        raise ValueError("Missing step_time_ms field")
    latency_ms = float(step_time_ms)
    worker_latencies_ms = _parse_worker_latencies(record.get("worker_latencies_ms"))
    if worker_latencies_ms is None:
        worker_latencies_ms = [latency_ms]

    loss_raw = record.get("loss")
    loss = float(loss_raw) if loss_raw is not None and loss_raw != "" else None
    gpu_util = _to_float(_pick(record, ["gpu_util_pct", "gpu_util", "gpu_usage_pct", "gpu_usage"]))
    gpu_mem_util = _to_float(_pick(record, ["gpu_mem_util_pct", "gpu_mem_util", "gpu_mem_pct"]))
    node = _to_optional_text(_pick(record, ["node", "node_name"]))
    gpu_model = _to_optional_text(_pick(record, ["gpu_model", "gpu_name"]))
    if gpu_mem_util is None:
        used = _to_float(_pick(record, ["gpu_mem_used_mb", "gpu_mem_used", "gpu_mem_used_mib"]))
        total = _to_float(_pick(record, ["gpu_mem_total_mb", "gpu_mem_total", "gpu_mem_total_mib"]))
        if used is not None and total is not None and total > 0:
            gpu_mem_util = (used / total) * 100.0

    return TelemetrySample(
        timestamp_ms=timestamp_ms,
        loss=loss,
        latency_ms=latency_ms,
        throughput=0.0,
        worker_latencies_ms=worker_latencies_ms,
        node=node,
        gpu_model=gpu_model,
        gpu_util_pct=gpu_util,
        gpu_mem_util_pct=gpu_mem_util,
    )


def _parse_ts_ms(value: object) -> int:
    # ISO8601 (naive -> UTC, 'Z' -> +00:00) + epoch seconds/ms (число или строка-число)
    if value is None:
        raise ValueError("Missing ts")

    if isinstance(value, (int, float)):
        v = float(value)
        return int(v) if v > 1e11 else int(v * 1000)

    s = str(value).strip()
    if not s:
        raise ValueError("Empty ts")

    if _NUMERIC_TS_RE.match(s):
        v = float(s)
        return int(v) if v > 1e11 else int(v * 1000)

    if s.endswith("Z"):
        s = s[:-1] + "+00:00"

    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


def _parse_worker_latencies(value: object) -> list[float] | None:
    raw = value
    if isinstance(raw, str):
        stripped = raw.strip()
        if not (stripped.startswith("[") and stripped.endswith("]")):
            return None
        try:
            raw = json.loads(stripped)
        except Exception:
            return None

    if not isinstance(raw, list) or not raw:
        return None

    try:
        parsed = [float(item) for item in raw]
    except (TypeError, ValueError):
        return None

    return parsed if parsed else None


def _pick(record: dict, keys: list[str]) -> object | None:
    for key in keys:
        if key in record:
            return record.get(key)
    return None


def _to_float(value: object) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("%"):
        text = text[:-1].strip()
    if text.lower().endswith("mib"):
        text = text[:-3].strip()
    if text.lower().endswith("mb"):
        text = text[:-2].strip()
    try:
        return float(text)
    except Exception:
        return None


def _to_optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
