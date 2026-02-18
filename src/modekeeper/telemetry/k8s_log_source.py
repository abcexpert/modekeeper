from __future__ import annotations

import json
import math
import os
import re
import subprocess
from pathlib import Path
from dataclasses import dataclass

from modekeeper.telemetry.file_source import _parse_ts_ms
from modekeeper.telemetry.models import TelemetrySample
from modekeeper.telemetry.raw_recorder import RawRecorder
from modekeeper.telemetry.sources import TelemetrySource

_KV_RE = re.compile(r"(?P<key>[A-Za-z0-9_]+)=(?P<value>[^\\s]+)")
_TELEMETRY_ANNOTATION = "modekeeper/telemetry"
_STDOUT_JSONL_MODE = "stdout-jsonl"

def _to_float(value: object) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.endswith('%'):
        text = text[:-1].strip()
    if text.lower().endswith('mib'):
        text = text[:-3].strip()
    if text.lower().endswith('mb'):
        text = text[:-2].strip()
    try:
        return float(text)
    except Exception:
        return None



def _run_cmd(argv: list[str], timeout_s: float = 20.0) -> dict:
    try:
        cp = subprocess.run(argv, capture_output=True, text=True, timeout=timeout_s)
        return {
            "argv": argv,
            "ok": cp.returncode == 0,
            "rc": cp.returncode,
            "stdout": cp.stdout,
            "stderr": cp.stderr,
            "error": None,
        }
    except FileNotFoundError as e:
        return {
            "argv": argv,
            "ok": False,
            "rc": 127,
            "stdout": "",
            "stderr": str(e),
            "error": "not_found",
        }
    except subprocess.TimeoutExpired as e:
        return {
            "argv": argv,
            "ok": False,
            "rc": 124,
            "stdout": e.stdout or "",
            "stderr": e.stderr or "",
            "error": "timeout",
        }


def _parse_kv_line(line: str) -> dict[str, str]:
    return {m.group("key"): m.group("value") for m in _KV_RE.finditer(line)}


def _normalize_number(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("ms"):
        return text[:-2]
    return text


def _parse_payload(payload: str) -> dict | None:
    if not payload:
        return None
    try:
        record = json.loads(payload)
        if isinstance(record, dict):
            return record
    except json.JSONDecodeError:
        pass
    kvs = _parse_kv_line(payload)
    return kvs or None

def _pick(record: dict, keys: list[str]) -> object | None:
    for k in keys:
        if k in record:
            return record.get(k)
    return None


def parse_k8s_log_lines(lines: list[str]) -> list[TelemetrySample]:
    samples: list[TelemetrySample] = []
    for raw in lines:
        line = raw.strip()
        if not line:
            continue

        ts_token: str | None = None
        payload = line
        if " " in line:
            first, rest = line.split(" ", 1)
            try:
                _parse_ts_ms(first)
                ts_token = first
                payload = rest.strip()
            except Exception:
                payload = line

        record = _parse_payload(payload) or _parse_payload(line)
        if not record:
            continue

        ts_value = record.get("ts") or record.get("t") or record.get("timestamp") or ts_token
        if ts_value is None:
            continue

        step_value = record.get("step_time_ms") or record.get("step_time") or record.get("latency_ms")
        if step_value is None:
            continue

        ts_ms = _parse_ts_ms(ts_value)
        step_text = _normalize_number(step_value)
        if step_text is None:
            continue
        step_time_ms = float(step_text)

        loss_raw = record.get("loss")
        loss_text = _normalize_number(loss_raw)
        loss = float(loss_text) if loss_text is not None else None

        gpu_util = _to_float(_pick(record, ["gpu_util_pct", "gpu_util", "gpu_usage_pct", "gpu_usage"]))
        gpu_mem_util = _to_float(_pick(record, ["gpu_mem_util_pct", "gpu_mem_util", "gpu_mem_pct"]))
        node = _to_optional_text(_pick(record, ["node", "node_name"]))
        gpu_model = _to_optional_text(_pick(record, ["gpu_model", "gpu_name"]))
        if gpu_mem_util is None:
            used = _to_float(_pick(record, ["gpu_mem_used_mb", "gpu_mem_used", "gpu_mem_used_mib"]))
            total = _to_float(_pick(record, ["gpu_mem_total_mb", "gpu_mem_total", "gpu_mem_total_mib"]))
            if used is not None and total is not None and total > 0:
                gpu_mem_util = (used / total) * 100.0

        samples.append(
            TelemetrySample(
                timestamp_ms=ts_ms,
                loss=loss,
                latency_ms=step_time_ms,
                throughput=0.0,
                worker_latencies_ms=[step_time_ms],
                node=node,
                gpu_model=gpu_model,
                gpu_util_pct=gpu_util,
                gpu_mem_util_pct=gpu_mem_util,
            )
        )
    return samples


def parse_k8s_stdout_jsonl(lines: list[str]) -> list[TelemetrySample]:
    samples: list[TelemetrySample] = []
    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        record = _parse_payload(line)
        if not isinstance(record, dict):
            continue
        ts_value = _pick(record, ["ts", "t", "timestamp"])
        step_value = _pick(record, ["step"])
        throughput_value = _pick(record, ["throughput", "samples_per_sec", "samples_sec"])
        if ts_value is None or step_value is None or throughput_value is None:
            continue
        try:
            ts_ms = _parse_ts_ms(ts_value)
            step = int(step_value)
            throughput = float(throughput_value)
        except Exception:
            continue
        if throughput <= 0:
            continue
        loss_raw = _pick(record, ["loss"])
        try:
            loss = float(loss_raw) if loss_raw is not None and str(loss_raw).strip() != "" else None
        except Exception:
            loss = None
        step_time_value = _pick(record, ["step_time_ms", "step_time", "latency_ms"])
        if step_time_value is None:
            latency_ms = 1000.0 / throughput
        else:
            try:
                step_text = _normalize_number(step_time_value)
                latency_ms = float(step_text) if step_text is not None else (1000.0 / throughput)
            except Exception:
                latency_ms = 1000.0 / throughput
        samples.append(
            TelemetrySample(
                timestamp_ms=ts_ms,
                step=step,
                loss=loss,
                latency_ms=latency_ms,
                throughput=throughput,
                worker_latencies_ms=[latency_ms],
            )
        )
    return samples


@dataclass
class K8sLogSource(TelemetrySource):
    namespace: str
    deployment: str
    container: str
    duration_ms: int
    record_raw_path: Path | None = None
    record_raw_mode: str = "w"
    timeout_s: float = 20.0
    rows_read: int = 0
    samples_parsed: int = 0
    error: str | None = None
    record_raw_lines_written: int = 0
    record_raw_error: str | None = None
    selected_pod_name: str | None = None
    selected_pod_node_name: str | None = None
    telemetry_mode_detected: str | None = None

    def _best_effort_get_deployment_telemetry_mode(self, kubectl_bin: str) -> str | None:
        argv = [
            kubectl_bin,
            "get",
            "deployment",
            self.deployment,
            "-n",
            self.namespace,
            "-o",
            "json",
        ]
        res = _run_cmd(argv, timeout_s=self.timeout_s)
        if res.get("rc") != 0:
            return None
        try:
            payload = json.loads(res.get("stdout") or "{}")
        except Exception:
            return None
        metadata = payload.get("metadata")
        if not isinstance(metadata, dict):
            return None
        annotations = metadata.get("annotations")
        if not isinstance(annotations, dict):
            return None
        return _to_optional_text(annotations.get(_TELEMETRY_ANNOTATION))

    def _best_effort_select_pod(self, kubectl_bin: str) -> tuple[str | None, str | None, str | None]:
        # Best-effort only; failures should not block logs collection.
        argv = [
            kubectl_bin,
            "get",
            "pods",
            "-n",
            self.namespace,
            "-l",
            f"app={self.deployment}",
            "-o",
            "json",
        ]
        res = _run_cmd(argv, timeout_s=self.timeout_s)
        if res.get("rc") != 0:
            return None, None, None
        try:
            payload = json.loads(res.get("stdout") or "{}")
        except Exception:
            return None, None, None
        items = payload.get("items")
        if not isinstance(items, list):
            return None, None, None
        candidates: list[tuple[str, str | None, str | None]] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            meta = item.get("metadata")
            spec = item.get("spec")
            if not isinstance(meta, dict) or not isinstance(spec, dict):
                continue
            pod_name = _to_optional_text(meta.get("name"))
            if pod_name is None:
                continue
            annotations = meta.get("annotations")
            telemetry_mode: str | None = None
            if isinstance(annotations, dict):
                telemetry_mode = _to_optional_text(annotations.get(_TELEMETRY_ANNOTATION))
            candidates.append((pod_name, _to_optional_text(spec.get("nodeName")), telemetry_mode))
        if not candidates:
            return None, None, None
        candidates.sort(key=lambda pair: pair[0])
        return candidates[0]

    def read(self) -> list[TelemetrySample]:
        recorder = RawRecorder(self.record_raw_path, mode=self.record_raw_mode)
        since_s = 0 if self.duration_ms == 0 else max(1, math.ceil(self.duration_ms / 1000.0))
        kubectl_bin = os.environ.get("KUBECTL", "kubectl")
        selected_pod_name, selected_pod_node_name, telemetry_mode = self._best_effort_select_pod(kubectl_bin)
        if telemetry_mode is None:
            telemetry_mode = self._best_effort_get_deployment_telemetry_mode(kubectl_bin)
        self.selected_pod_name = selected_pod_name
        self.selected_pod_node_name = selected_pod_node_name
        self.telemetry_mode_detected = telemetry_mode
        argv = [
            kubectl_bin,
            "logs",
            "-n",
            self.namespace,
            (
                f"pod/{selected_pod_name}"
                if selected_pod_name
                else f"deployment/{self.deployment}"
            ),
        ]
        container = str(self.container or "").strip()
        if container and container != "auto":
            argv += ["-c", container]
        argv += ["--since", f"{since_s}s"]

        res = _run_cmd(argv, timeout_s=self.timeout_s)
        try:
            if res.get("rc") != 0:
                self.error = res.get("stderr") or res.get("error") or "kubectl logs failed"
                self.rows_read = 0
                self.samples_parsed = 0
                return []

            raw_text = res.get("stdout") or ""
            for line in raw_text.splitlines(keepends=True):
                recorder.write_line(line)
            lines = raw_text.splitlines()
            self.rows_read = len(lines)
            if telemetry_mode == _STDOUT_JSONL_MODE:
                samples = parse_k8s_stdout_jsonl(lines)
            else:
                samples = parse_k8s_log_lines(lines)
            if selected_pod_node_name:
                for sample in samples:
                    if sample.node is None:
                        sample.node = selected_pod_node_name
            self.samples_parsed = len(samples)
            return samples
        finally:
            recorder.close()
            self.record_raw_lines_written = recorder.lines_written
            self.record_raw_error = recorder.error


def _to_optional_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
