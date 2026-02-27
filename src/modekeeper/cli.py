"""Command-line interface for ModeKeeper."""

from __future__ import annotations


import argparse
from . import __version__ as MK_VERSION
import errno
import gzip
import hashlib
import json
import os
import shutil
import re
import socket
import subprocess
import sys
import tarfile
import time
import signal
from dataclasses import asdict
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from io import BytesIO
from pathlib import Path

from modekeeper import __version__ as MK_VERSION
from modekeeper.knobs import ActuatorRegistry, Knob
from modekeeper.adapters.kubernetes import build_k8s_plan
from modekeeper.audit.decision_trace import DecisionTraceWriter
from modekeeper.audit.decision_trace import SCHEMA_VERSION as DECISION_TRACE_SCHEMA_VERSION
from modekeeper.core.analysis import analyze_signals
from modekeeper.core.cost_model import CostModelV0, get_default_cost_model
from modekeeper.core.modes import Mode
from modekeeper.core.opportunity import estimate_opportunity
from modekeeper.core.state_machine import ModeStateMachine
from modekeeper.core.summary import summarize_decision, summarize_observe
from modekeeper.core.value_summary import build_value_summary
from modekeeper.demo.mk068_demo import run_mk068_demo
from modekeeper.demo.runner import run_demo
from modekeeper.chords.catalog import validate_catalog_file
from modekeeper.fleet.inventory import collect_inventory
from modekeeper.fleet.policy_propagation import collect_policy_propagation
from modekeeper.k8s.rbac_diagnostics import parse_k8s_forbidden
from modekeeper.license.verify import verify_license
from modekeeper.passports import (
    PassportValidationError,
    list_templates as passports_list_templates,
    load_passport,
    load_template,
)
from modekeeper.passports.observe_max import build_observe_max_artifacts
from modekeeper.policy.bundle import (
    build_policy_bundle,
    sha256_file,
    write_policy_bundle,
)
from modekeeper.policy.rules import propose_actions
from modekeeper.roi.estimate import estimate_roi
from modekeeper.roi.mk074_before_after import build_mk074_before_after
from modekeeper.safety.explain import ExplainLog
from modekeeper.safety.guards import Guardrails, split_actions_by_approval
from modekeeper.telemetry.collector import TelemetryCollector
from modekeeper.telemetry.file_source import FileSource
from modekeeper.telemetry.k8s_log_source import K8sLogSource
from modekeeper.telemetry.sources import SyntheticSource


_MAX_TELEMETRY_POINTS = 2000
_DRIFT_K8S_TARGETS = {
    "grad_accum_steps": 8,
    "microbatch_size": 32,
}
_KNOB_ANNOTATION_PREFIX = "modekeeper/knob."


def _parse_duration_ms(value: str) -> int:
    raw = value
    text = value.strip().lower()
    if not text:
        raise argparse.ArgumentTypeError(
            f"invalid duration: '{raw}' (use e.g. 1.5s or 250ms)"
        )

    unit = "s"
    number = text
    if text.endswith("ms"):
        unit = "ms"
        number = text[:-2]
    elif text.endswith("s"):
        unit = "s"
        number = text[:-1]
    elif text.endswith("m"):
        unit = "m"
        number = text[:-1]
    elif text.endswith("h"):
        unit = "h"
        number = text[:-1]

    if not number:
        raise argparse.ArgumentTypeError(
            f"invalid duration: '{raw}' (use e.g. 1.5s or 250ms)"
        )

    try:
        parsed = Decimal(number)
    except InvalidOperation as exc:
        raise argparse.ArgumentTypeError(
            f"invalid duration: '{raw}' (use e.g. 1.5s or 250ms)"
        ) from exc

    if parsed < 0:
        raise argparse.ArgumentTypeError(
            f"invalid duration: '{raw}' (use e.g. 1.5s or 250ms)"
        )

    multipliers = {
        "ms": Decimal(1),
        "s": Decimal(1000),
        "m": Decimal(60_000),
        "h": Decimal(3_600_000),
    }
    duration_ms = parsed * multipliers[unit]
    if duration_ms != duration_ms.to_integral_value():
        raise argparse.ArgumentTypeError(
            f"invalid duration: '{raw}' (use e.g. 1.5s or 250ms)"
        )
    return int(duration_ms)


def _parse_env_float(name: str, default: float | None) -> float | None:
    raw = os.environ.get(name)
    if raw is None or not str(raw).strip():
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _parse_env_int(name: str, default: int | None) -> int | None:
    raw = os.environ.get(name)
    if raw is None or not str(raw).strip():
        return default
    try:
        return int(raw)
    except ValueError:
        return default


def _get_cost_model() -> CostModelV0:
    base = get_default_cost_model()
    return {
        **base,
        "usd_per_gpu_hour": _parse_env_float("MODEKEEPER_GPU_HOUR_USD", base["usd_per_gpu_hour"]),
        "gpus_per_job": _parse_env_int("MODEKEEPER_GPU_COUNT", base["gpus_per_job"]),
    }


def _get_opportunity_cost_model() -> dict:
    cost_model = _get_cost_model()
    gpu_hour_usd = cost_model.get("usd_per_gpu_hour")
    gpu_count = cost_model.get("gpus_per_job")
    return {
        "gpu_hour_usd": float(gpu_hour_usd) if isinstance(gpu_hour_usd, (int, float)) else 0.0,
        "gpu_count": int(gpu_count) if isinstance(gpu_count, int) else 0,
    }


def _duration_ms_to_seconds(duration_ms: int) -> int | float:
    if duration_ms % 1000 == 0:
        return duration_ms // 1000
    return duration_ms / 1000.0


def _downsample_indices(total: int, limit: int) -> list[int]:
    if total <= 0 or limit <= 0:
        return []
    if total <= limit:
        return list(range(total))
    if limit == 1:
        return [total - 1]
    return [int(i * (total - 1) / (limit - 1)) for i in range(limit)]


def _build_telemetry_payload(samples: list[object], limit: int = _MAX_TELEMETRY_POINTS) -> dict:
    points: list[dict] = []
    for idx in _downsample_indices(len(samples), limit):
        sample = samples[idx]
        point = {
            "ts_ms": int(getattr(sample, "timestamp_ms")),
            "latency_ms": float(getattr(sample, "latency_ms")),
            "loss": (
                float(getattr(sample, "loss"))
                if getattr(sample, "loss", None) is not None
                else None
            ),
            "gpu_util_pct": (
                float(getattr(sample, "gpu_util_pct"))
                if getattr(sample, "gpu_util_pct", None) is not None
                else None
            ),
            "gpu_mem_util_pct": (
                float(getattr(sample, "gpu_mem_util_pct"))
                if getattr(sample, "gpu_mem_util_pct", None) is not None
                else None
            ),
            "throughput": float(getattr(sample, "throughput", 0.0)),
        }
        step = getattr(sample, "step", None)
        if isinstance(step, int):
            point["step"] = step
        node = getattr(sample, "node", None)
        if isinstance(node, str) and node.strip():
            point["node"] = node.strip()
        gpu_model = getattr(sample, "gpu_model", None)
        if isinstance(gpu_model, str) and gpu_model.strip():
            point["gpu_model"] = gpu_model.strip()
        points.append(point)
    return {
        "sample_count": len(samples),
        "points": points,
    }


def _has_loss_and_throughput(samples: list[object]) -> bool:
    for sample in samples:
        loss = getattr(sample, "loss", None)
        throughput = getattr(sample, "throughput", None)
        if loss is None:
            continue
        if isinstance(throughput, (int, float)) and float(throughput) > 0.0:
            return True
    return False


def _build_environment_fingerprint(samples: list[object]) -> dict:
    nodes_seen: set[str] = set()
    gpu_models_seen: set[str] = set()
    for sample in samples:
        node = getattr(sample, "node", None)
        if isinstance(node, str):
            node = node.strip()
            if node:
                nodes_seen.add(node)
        gpu_model = getattr(sample, "gpu_model", None)
        if isinstance(gpu_model, str):
            gpu_model = gpu_model.strip()
            if gpu_model:
                gpu_models_seen.add(gpu_model)
    nodes = sorted(nodes_seen)
    gpu_models = sorted(gpu_models_seen)
    unstable = (len(nodes) > 1) or (len(gpu_models) > 1)
    notes: list[str] = []
    if len(nodes) > 1:
        notes.append("multiple_nodes_seen")
    if len(gpu_models) > 1:
        notes.append("multiple_gpu_models_seen")
    return {
        "nodes_seen": nodes,
        "gpu_models_seen": gpu_models,
        "unstable": unstable,
        "notes": notes,
    }


def _ensure_out_dir(out_dir: str) -> Path:
    path = Path(out_dir)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _format_utc(dt: datetime) -> str:
    return dt.isoformat(timespec="seconds")


def _env_truthy(name: str) -> bool:
    value = os.environ.get(name, "").strip().lower()
    if value in {"", "0", "false", "no", "off"}:
        return False
    return True


_KILL_SWITCH_ERROR_LINE = "ERROR: MODEKEEPER_KILL_SWITCH=1 blocks apply/mutate operations"
_VERIFY_GATE_ERROR_LINE = "ERROR: verify_ok=true is required for apply/mutate operations"
_KILL_SWITCH_BLOCK_REASON = "kill_switch_active"
_KILL_SWITCH_ENV_SIGNAL = "env:MODEKEEPER_KILL_SWITCH"
_KILL_SWITCH_UNRELIABLE_SIGNAL = "kill_switch_unreliable"
_LICENSE_ENV_VAR = "MODEKEEPER_LICENSE_PATH"
_LICENSE_CWD_FILENAME = "modekeeper.license.json"
_MODEKEEPER_HOME_CONFIG_DIR = Path(".config") / "modekeeper"
_LICENSE_VERIFY_DEFAULT_FILENAME = "license.json"
_LICENSE_PUBLIC_KEYS_DEFAULT_FILENAME = "license_public_keys.json"
_LICENSE_PUBLIC_KEYS_ENV_VAR = "MODEKEEPER_LICENSE_PUBLIC_KEYS_PATH"
_APPLY_BLOCK_ERROR_LINES = {
    "license_missing": (
        "ERROR: apply blocked: license_missing "
        "(use --license-path, MODEKEEPER_LICENSE_PATH, or ./modekeeper.license.json)"
    ),
    "license_invalid": "ERROR: apply blocked: license_invalid",
    "verify_failed": _VERIFY_GATE_ERROR_LINE,
    "verify_missing": _VERIFY_GATE_ERROR_LINE,
    _KILL_SWITCH_BLOCK_REASON: _KILL_SWITCH_ERROR_LINE,
}
_PRO_REQUIRED_REASON = "pro_required"


def _emit_kill_switch_error() -> None:
    print(_KILL_SWITCH_ERROR_LINE, file=sys.stderr)


def _emit_apply_block_error(reason: str | None) -> None:
    line = _APPLY_BLOCK_ERROR_LINES.get(str(reason or ""))
    if line:
        print(line, file=sys.stderr)


def _is_verify_gate_reason(reason: str | None) -> bool:
    return str(reason or "") in {"verify_failed", "verify_missing"}


def _evaluate_kill_switch_signal() -> dict[str, object]:
    """Fail-closed kill-switch evaluation shared by all apply entrypoints."""
    try:
        raw = os.environ.get("MODEKEEPER_KILL_SWITCH")
    except Exception:
        return {
            "active": True,
            "signal": _KILL_SWITCH_UNRELIABLE_SIGNAL,
            "reliable": False,
        }
    if raw is None:
        return {
            "active": False,
            "signal": None,
            "reliable": True,
        }
    return {
        "active": True,
        "signal": _KILL_SWITCH_ENV_SIGNAL,
        "reliable": True,
    }


def _require_pro(feature: str) -> int:
    print(f"PRO REQUIRED: {feature}", file=sys.stderr)
    return 2


def _load_pro_cli_ext() -> object | None:
    return None


def _is_internal_paid_override() -> bool:
    return (
        os.environ.get("MODEKEEPER_INTERNAL_OVERRIDE") == "1"
        and os.environ.get("MODEKEEPER_PAID") == "1"
    )


def _resolve_license_path(cli_license_path: str | None) -> Path | None:
    if isinstance(cli_license_path, str) and cli_license_path.strip():
        return Path(cli_license_path.strip())

    env_path = (os.environ.get(_LICENSE_ENV_VAR) or "").strip()
    if env_path:
        return Path(env_path)

    cwd_default = Path.cwd() / _LICENSE_CWD_FILENAME
    if cwd_default.exists():
        return cwd_default
    return None


def _home_modekeeper_config_path(filename: str) -> Path:
    home_dir = Path.home()
    return home_dir / _MODEKEEPER_HOME_CONFIG_DIR / filename


def _resolve_license_verify_path(cli_license_path: str | None) -> Path:
    if isinstance(cli_license_path, str) and cli_license_path.strip():
        return Path(cli_license_path.strip())
    env_path = (os.environ.get(_LICENSE_ENV_VAR) or "").strip()
    if env_path:
        return Path(env_path)
    return _home_modekeeper_config_path(_LICENSE_VERIFY_DEFAULT_FILENAME)


def _resolve_apply_license_gate(*, kubectl: str, license_path: Path | None = None) -> dict:
    if _is_internal_paid_override():
        return {
            "license_ok": True,
            "reason": "ok",
            "expires_at": None,
            "entitlements_summary": ["apply"],
            "block_reason": None,
            "license_path": None,
            "internal_override": True,
        }

    resolved_license_path = license_path
    if resolved_license_path is None:
        resolved_license_path = _resolve_license_path(None)
    if resolved_license_path is None:
        return {
            "license_ok": False,
            "reason": "license_missing",
            "expires_at": None,
            "entitlements_summary": [],
            "block_reason": "license_missing",
            "license_path": None,
            "internal_override": False,
        }

    verify = verify_license(resolved_license_path, kubectl=kubectl)
    entitlements_summary = verify.get("entitlements_summary")
    entitlements: list[str] = (
        list(entitlements_summary)
        if isinstance(entitlements_summary, list)
        and all(isinstance(item, str) for item in entitlements_summary)
        else []
    )

    block_reason: str | None = None
    license_ok = bool(verify.get("license_ok") is True)
    reason = str(verify.get("reason") or "")
    if not license_ok:
        if reason == "license_expired":
            block_reason = "license_expired"
        elif reason == "binding_mismatch":
            block_reason = "binding_mismatch"
        else:
            block_reason = "license_invalid"
    elif "apply" not in entitlements:
        block_reason = "entitlement_missing"

    return {
        "license_ok": license_ok,
        "reason": reason,
        "expires_at": verify.get("expires_at"),
        "entitlements_summary": entitlements,
        "block_reason": block_reason,
        "license_path": str(resolved_license_path),
        "internal_override": False,
    }


def _bash_single_quote(text: str) -> str:
    return text.replace("'", "'\\''")


def _infer_uniform_value(items: list[object], key: str) -> str:
    if not items:
        return "mixed"
    values: set[object] = set()
    for item in items:
        if not isinstance(item, dict):
            return "mixed"
        values.add(item.get(key))
    if len(values) != 1:
        return "mixed"
    value = next(iter(values))
    if value is None:
        return "mixed"
    return str(value)


def _validate_k8s_plan(plan: list[object]) -> tuple[list[dict], str | None, int | None]:
    normalized: list[dict] = []
    for idx, item in enumerate(plan):
        if not isinstance(item, dict):
            return [], f"plan item at index {idx} must be an object", idx
        namespace = item.get("namespace")
        if not isinstance(namespace, str) or not namespace.strip():
            return [], f"plan item at index {idx} has invalid namespace", idx
        name = item.get("name")
        if not isinstance(name, str) or not name.strip():
            return [], f"plan item at index {idx} has invalid name", idx
        patch = item.get("patch")
        if patch is None:
            patch = {}
        if not isinstance(patch, dict):
            return [], f"plan item at index {idx} has invalid patch", idx
        normalized.append(
            {
                "namespace": namespace,
                "name": name,
                "patch": patch,
            }
        )
    return normalized, None, None


def _extract_k8s_plan_items(
    payload: object, *, command: str
) -> tuple[list[object] | None, bool, str | None]:
    if isinstance(payload, list):
        return payload, False, None
    if isinstance(payload, dict):
        if "items" in payload:
            items = payload.get("items")
            if not isinstance(items, list):
                return None, False, f"{command} expects plan.items to be a list when using envelope form"
            return items, False, None
        return [payload], True, None
    return None, False, f"{command} expects plan JSON to be a list, a single plan object, or an envelope with items"


def _k8s_object(namespace: str, name: str, kind: str = "Deployment") -> dict:
    return {
        "namespace": namespace,
        "name": name,
        "kind": kind,
    }


def _k8s_objects_from_plan(plan: list[dict], kind: str = "Deployment") -> list[dict]:
    return [_k8s_object(item["namespace"], item["name"], kind=kind) for item in plan]


# --- k8s verify helpers ---
def _run_cmd(argv: list[str], timeout_s: float = 20.0) -> dict:
    """Run command capturing stdout/stderr. Never raises; returns a dict."""
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


def _kubectl(args: list[str], timeout_s: float = 20.0) -> dict:
    kubectl_bin = os.environ.get("KUBECTL", "kubectl")
    return _run_cmd([kubectl_bin, *args], timeout_s=timeout_s)
# --- end k8s verify helpers ---


def _resolve_drift_k8s_mode(namespace: str, deployment: str) -> bool:
    kubectl_path = (os.environ.get("KUBECTL") or "").strip()
    return bool(kubectl_path and namespace.strip() and deployment.strip())


def _read_k8s_deployment_template_knobs(
    *,
    namespace: str,
    deployment: str,
) -> dict[str, int | None] | None:
    res = _kubectl(["-n", namespace, "get", f"deployment/{deployment}", "-o", "json"])
    if res.get("rc") != 0:
        return None
    try:
        payload = json.loads(res.get("stdout") or "{}")
    except Exception:
        return None
    annotations = (
        payload.get("spec", {})
        .get("template", {})
        .get("metadata", {})
        .get("annotations", {})
    )
    if not isinstance(annotations, dict):
        return None

    knobs: dict[str, int | None] = {}
    for knob in _DRIFT_K8S_TARGETS:
        raw = annotations.get(f"{_KNOB_ANNOTATION_PREFIX}{knob}")
        if raw is None:
            knobs[knob] = None
            continue
        try:
            knobs[knob] = int(str(raw).strip())
        except Exception:
            knobs[knob] = None
    return knobs


def _build_k8s_drift_signal_from_knobs(observed_knobs: dict[str, int | None]) -> tuple[dict, bool]:
    drift = any(observed_knobs.get(knob) != target for knob, target in _DRIFT_K8S_TARGETS.items())
    notes: list[str] = ["k8s_deployment_template_knobs"]
    if drift:
        notes.append("k8s_knob_drift")
    return (
        {
            "drift": drift,
            "burst": False,
            "straggler": False,
            "gpu_saturated": False,
            "incident": drift,
            "stable": not drift,
            "notes": notes,
        },
        drift,
    )


def _emit_k8s_verify_diagnostic(
    explain: ExplainLog,
    name: str,
    *,
    error: str,
    namespace: str | None = None,
    rc: int | None = None,
    stderr: str | None = None,
    detail: str | None = None,
) -> None:
    payload: dict[str, object] = {"name": name, "error": error}
    if namespace:
        payload["namespace"] = namespace
    if rc is not None:
        payload["rc"] = rc
    if stderr:
        payload["stderr"] = stderr
    if detail:
        payload["detail"] = detail
    explain.emit("k8s_verify_diagnostic", payload)


def _parse_kubectl_version_json(stdout: str, key: str) -> str | None:
    text = (stdout or "").strip()
    if not text or not text.startswith("{"):
        return None
    try:
        payload = json.loads(text)
    except Exception:
        return None
    version = payload.get(key)
    if isinstance(version, dict):
        git_version = version.get("gitVersion")
        if isinstance(git_version, str) and git_version.strip():
            return git_version.strip()
    return None


def _parse_kubectl_version_text(stdout: str, prefix: str) -> str | None:
    text = (stdout or "").strip()
    if not text:
        return None
    for line in text.splitlines():
        if prefix in line:
            match = re.search(rf"{re.escape(prefix)}\s*:\s*(\S+)", line)
            if match:
                return match.group(1).strip()
    return None


def _collect_k8s_verify_diagnostics(
    *,
    k8s_namespaces: list[str],
    kubectl_present: bool,
    explain: ExplainLog,
) -> dict:
    namespaces = [ns for ns in k8s_namespaces if isinstance(ns, str) and ns.strip()]
    is_mixed = len(namespaces) != 1
    diagnostics = {
        "kubectl_version": None,
        "server_version": None,
        "auth_can_i_patch_deployments": None,
        "auth_can_i_get_deployments": None,
        "auth_can_i_patch_deployments_by_namespace": {ns: None for ns in namespaces},
        "auth_can_i_get_deployments_by_namespace": {ns: None for ns in namespaces},
    }

    if not kubectl_present:
        _emit_k8s_verify_diagnostic(
            explain,
            "kubectl_version",
            error="kubectl_not_found",
        )
        _emit_k8s_verify_diagnostic(
            explain,
            "server_version",
            error="kubectl_not_found",
        )
        if is_mixed:
            for ns in namespaces:
                _emit_k8s_verify_diagnostic(
                    explain,
                    "auth_can_i_patch_deployments",
                    error="kubectl_not_found",
                    namespace=ns,
                )
                _emit_k8s_verify_diagnostic(
                    explain,
                    "auth_can_i_get_deployments",
                    error="kubectl_not_found",
                    namespace=ns,
                )
        else:
            _emit_k8s_verify_diagnostic(
                explain,
                "auth_can_i_patch_deployments",
                error="kubectl_not_found",
            )
            _emit_k8s_verify_diagnostic(
                explain,
                "auth_can_i_get_deployments",
                error="kubectl_not_found",
            )
        return diagnostics

    try:
        res = _kubectl(["version", "--client", "-o", "json"])
        version = _parse_kubectl_version_json(res.get("stdout") or "", "clientVersion")
        if not version:
            fallback = _kubectl(["version", "--client", "--short"])
            version = _parse_kubectl_version_text(fallback.get("stdout") or "", "Client Version")
            if not version:
                _emit_k8s_verify_diagnostic(
                    explain,
                    "kubectl_version",
                    error="client_version_unavailable",
                    rc=fallback.get("rc"),
                    stderr=(fallback.get("stderr") or "").strip() or None,
                    detail="failed to parse kubectl client version",
                )
        if version:
            diagnostics["kubectl_version"] = version
        elif res.get("rc") not in (0, None):
            _emit_k8s_verify_diagnostic(
                explain,
                "kubectl_version",
                error="client_version_failed",
                rc=res.get("rc"),
                stderr=(res.get("stderr") or "").strip() or None,
            )
    except Exception as exc:
        _emit_k8s_verify_diagnostic(
            explain,
            "kubectl_version",
            error="client_version_exception",
            detail=str(exc),
        )

    try:
        res = _kubectl(["version", "-o", "json"])
        version = _parse_kubectl_version_json(res.get("stdout") or "", "serverVersion")
        if version:
            diagnostics["server_version"] = version
        else:
            if res.get("rc") == 0:
                _emit_k8s_verify_diagnostic(
                    explain,
                    "server_version",
                    error="server_version_unavailable",
                    detail="server version missing from kubectl output",
                )
            else:
                _emit_k8s_verify_diagnostic(
                    explain,
                    "server_version",
                    error="server_version_failed",
                    rc=res.get("rc"),
                    stderr=(res.get("stderr") or "").strip() or None,
                )
    except Exception as exc:
        _emit_k8s_verify_diagnostic(
            explain,
            "server_version",
            error="server_version_exception",
            detail=str(exc),
        )

    if not namespaces:
        return diagnostics

    def _run_auth_can_i(verb: str, resource: str, name: str, namespace: str) -> None:
        try:
            res = _kubectl(
                [
                    "-n",
                    namespace,
                    "auth",
                    "can-i",
                    verb,
                    resource,
                ]
            )
            parsed = _parse_auth_can_i_answer(res.get("stdout") or "")
            if parsed is not None:
                if not is_mixed:
                    diagnostics[name] = parsed
                by_ns_key = f"{name}_by_namespace"
                by_ns = diagnostics.get(by_ns_key)
                if isinstance(by_ns, dict):
                    by_ns[namespace] = parsed
            else:
                rc = res.get("rc")
                stdout = (res.get("stdout") or "").strip()
                stderr = (res.get("stderr") or "").strip()
                _emit_k8s_verify_diagnostic(
                    explain,
                    name,
                    error="auth_can_i_unexpected_output",
                    namespace=namespace if is_mixed else None,
                    rc=rc,
                    stderr=stderr or None,
                    detail=(
                        f"rc={rc}; stdout={stdout or '<empty>'}; stderr={stderr or '<empty>'}"
                    ),
                )
        except Exception as exc:
            _emit_k8s_verify_diagnostic(
                explain,
                name,
                error="auth_can_i_exception",
                namespace=namespace if is_mixed else None,
                detail=str(exc),
            )

    for ns in namespaces:
        _run_auth_can_i("patch", "deployments", "auth_can_i_patch_deployments", ns)
        _run_auth_can_i("get", "deployments", "auth_can_i_get_deployments", ns)
    return diagnostics


def _parse_auth_can_i_answer(stdout: str) -> bool | None:
    text = (stdout or "").strip()
    if not text:
        return None

    if text.startswith("{"):
        try:
            payload = json.loads(text)
        except Exception:
            payload = None
        if isinstance(payload, dict):
            status = payload.get("status")
            if isinstance(status, dict):
                allowed = status.get("allowed")
                if isinstance(allowed, bool):
                    return allowed
            allowed = payload.get("allowed")
            if isinstance(allowed, bool):
                return allowed
        return None

    non_empty_lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not non_empty_lines:
        return None
    answer = non_empty_lines[-1].lower()
    if answer == "yes":
        return True
    if answer == "no":
        return False
    return None


def _summarize_verify_detail(rc: int | None, stderr: str | None) -> str | None:
    parts: list[str] = []
    if rc is not None:
        parts.append(f"rc={rc}")
    if stderr:
        text = stderr.strip()
        if len(text) > 160:
            text = text[:157] + "..."
        parts.append(f"stderr={text}")
    if not parts:
        return None
    return "; ".join(parts)


def _classify_k8s_verify_dry_run_failure(stderr: str | None) -> str:
    text = (stderr or "").strip()
    lower = text.lower()
    if "(forbidden)" in text or "forbidden" in lower or "cannot patch" in lower:
        return "rbac_denied"
    if "notfound" in lower or "not found" in lower:
        if "namespace" in lower:
            return "namespace_missing"
        return "deployment_missing"
    return "dry_run_failed"


def _ensure_report_details(report_base: dict) -> dict:
    details = report_base.get("details")
    if isinstance(details, dict):
        return details
    details = {}
    report_base["details"] = details
    return details


def _parse_first_k8s_forbidden(texts: list[str | None]) -> dict | None:
    for text in texts:
        if not isinstance(text, str) or not text.strip():
            continue
        parsed = parse_k8s_forbidden(text)
        if parsed is not None:
            return parsed
    return None


def _extract_verify_rbac_diagnostics(verify_blocker: dict | None, items_checks: list[dict]) -> dict | None:
    if not isinstance(verify_blocker, dict) or verify_blocker.get("kind") != "rbac_denied":
        return None
    texts: list[str | None] = []
    blocker_index = verify_blocker.get("index")
    if isinstance(blocker_index, int) and 0 <= blocker_index < len(items_checks):
        dry_run = items_checks[blocker_index].get("dry_run")
        if isinstance(dry_run, dict):
            texts.append(dry_run.get("stderr"))
    for item in items_checks:
        dry_run = item.get("dry_run")
        if isinstance(dry_run, dict):
            texts.append(dry_run.get("stderr"))
    return _parse_first_k8s_forbidden(texts)


def _select_k8s_verify_blocker(
    *,
    ok: bool,
    kubectl_present: bool,
    items_checks: list[dict],
) -> dict | None:
    if ok:
        return None
    if not kubectl_present:
        return {
            "kind": "kubectl_missing",
            "index": None,
            "namespace": None,
            "name": None,
            "detail": None,
        }
    for idx, item in enumerate(items_checks):
        if not item.get("namespace_exists"):
            return {
                "kind": "namespace_missing",
                "index": idx,
                "namespace": item.get("namespace"),
                "name": item.get("name"),
                "detail": None,
            }
    for idx, item in enumerate(items_checks):
        if not item.get("deployment_exists"):
            return {
                "kind": "deployment_missing",
                "index": idx,
                "namespace": item.get("namespace"),
                "name": item.get("name"),
                "detail": None,
            }
    for idx, item in enumerate(items_checks):
        dry_run = item.get("dry_run") or {}
        if dry_run.get("attempted") and not dry_run.get("ok"):
            detail = _summarize_verify_detail(dry_run.get("rc"), dry_run.get("stderr"))
            kind = _classify_k8s_verify_dry_run_failure(dry_run.get("stderr"))
            return {
                "kind": kind,
                "index": idx,
                "namespace": item.get("namespace"),
                "name": item.get("name"),
                "detail": detail,
            }
    return {
        "kind": "unknown",
        "index": None,
        "namespace": None,
        "name": None,
        "detail": None,
    }


def _write_kubectl_plan(
    out_dir: Path,
    plan: list[object],
    namespace: str,
    deployment: str,
) -> Path:
    k8s_kubectl_plan_path = out_dir / "k8s_plan.kubectl.sh"
    if not plan:
        kubectl_lines = [
            "#!/usr/bin/env bash",
            "set -Eeuo pipefail",
            "# Plan-only: empty plan (no actions).",
            'echo "ModeKeeper plan-only script: empty plan (no actions)." >&2',
            "",
        ]
    else:
        kubectl_lines = [
            "#!/usr/bin/env bash",
            "set -Eeuo pipefail",
            "# Plan-only: not executed by ModeKeeper",
            'echo "ModeKeeper K8s plan-only script (NOT executed automatically). Review before running." >&2',
            f'echo "Target: namespace={namespace} deployment={deployment}" >&2',
            'echo "Current kubectl context:" >&2',
            "kubectl config current-context >&2 || true",
            "",
        ]
    for item in plan:
        item_namespace = item.get("namespace")
        name = item.get("name")
        patch = item.get("patch", {})
        patch_json = json.dumps(patch, ensure_ascii=False)
        patch_json = _bash_single_quote(patch_json)
        kubectl_lines.append(
            f"kubectl -n {item_namespace} patch deployment/{name} --type merge -p '{patch_json}'"
        )
    k8s_kubectl_plan_path.write_text(
        "\n".join(kubectl_lines) + "\n",
        encoding="utf-8",
    )
    k8s_kubectl_plan_path.chmod(0o755)
    return k8s_kubectl_plan_path


def _build_report(
    base: dict,
    *,
    started_at: datetime,
    finished_at: datetime,
    out_dir: Path,
    mode: str,
    apply_requested: bool,
    dry_run: bool,
) -> dict:
    duration_s = int((finished_at - started_at).total_seconds())
    report = {
        "schema_version": "v0",
        "started_at": _format_utc(started_at),
        "finished_at": _format_utc(finished_at),
        "duration_s": duration_s,
        "out_dir": str(out_dir),
        "mode": mode,
        "apply_requested": bool(apply_requested),
        "dry_run": bool(dry_run),
    }
    report.update(base)
    report["apply_requested"] = bool(apply_requested)
    report["dry_run"] = bool(dry_run)
    return report


def _count_blocked_reasons(results: list[object]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for result in results:
        if isinstance(result, dict):
            blocked = bool(result.get("blocked", False))
            reason = result.get("reason", "")
        else:
            blocked = getattr(result, "blocked", False)
            reason = getattr(result, "reason", "")
        if not blocked:
            continue
        if isinstance(reason, str):
            reason = reason.strip()
        else:
            reason = ""
        if not reason:
            reason = "unknown"
        counts[reason] = counts.get(reason, 0) + 1
    return counts


def _count_applied_reasons(results: list[object]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for result in results:
        if isinstance(result, dict):
            applied = bool(result.get("applied", False))
            reason = result.get("reason", "")
        else:
            applied = getattr(result, "applied", False)
            reason = getattr(result, "reason", "")
        if not applied:
            continue
        if isinstance(reason, str):
            reason = reason.strip()
        else:
            reason = ""
        if not reason:
            reason = "unknown"
        counts[reason] = counts.get(reason, 0) + 1
    return counts


def _write_report(
    out_dir: Path,
    report: dict,
    prefix: str,
    *,
    latest_name: str | None = None,
) -> Path:
    ts = _utc_now().strftime("%Y%m%d_%H%M%S")
    report_path = out_dir / f"{prefix}_{ts}.json"
    report_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    if latest_name:
        latest_path = out_dir / latest_name
        shutil.copyfile(report_path, latest_path)
    return report_path


def _write_json_report(path: Path, payload: dict) -> None:
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _report_ts() -> str:
    return _utc_now().strftime("%Y%m%d_%H%M%S")


def _write_latest_with_timestamp(
    out_dir: Path,
    *,
    latest_name: str,
    prefix: str,
    payload: dict,
) -> tuple[Path, Path]:
    ts_path = out_dir / f"{prefix}_{_report_ts()}.json"
    latest_path = out_dir / latest_name
    _write_json_report(ts_path, payload)
    _write_json_report(latest_path, payload)
    return latest_path, ts_path


def _write_summary_aliases(out_dir: Path, *, legacy_name: str, text: str) -> tuple[Path, Path]:
    legacy_path = out_dir / legacy_name
    summary_path = out_dir / "summary.md"
    legacy_path.write_text(text, encoding="utf-8")
    summary_path.write_text(text, encoding="utf-8")
    return summary_path, legacy_path


def _resolve_inputs_root(out_dir: Path, explicit: str | None) -> Path:
    if isinstance(explicit, str) and explicit.strip():
        return Path(explicit).resolve()
    return out_dir.parent.resolve()


def _find_and_read_json(root: Path, name: str) -> tuple[Path | None, dict | None]:
    path = _find_first_named(root, name)
    if path is None:
        return None, None
    payload, error = _read_json_best_effort(path)
    if error:
        return path, None
    return path, payload


def _try_git_commit(repo_root: Path) -> str | None:
    try:
        cp = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
            cwd=repo_root,
        )
    except Exception:
        return None
    if cp.returncode != 0:
        return None
    commit = (cp.stdout or "").strip()
    return commit if commit else None


def _try_git_dirty(repo_root: Path) -> bool:
    try:
        cp = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True,
            text=True,
            check=False,
            cwd=repo_root,
        )
    except Exception:
        return False
    if cp.returncode != 0:
        return False
    return bool((cp.stdout or "").strip())


def _resolve_verify_report_for_bundle(out_dir: Path) -> Path | None:
    latest_verify = out_dir / "k8s_verify_latest.json"
    if latest_verify.exists():
        return latest_verify

    closed_loop_latest = out_dir / "closed_loop_latest.json"
    if not closed_loop_latest.exists():
        return None
    try:
        payload = json.loads(closed_loop_latest.read_text(encoding="utf-8"))
    except Exception:
        return None
    verify_path_value = payload.get("k8s_verify_report_path") if isinstance(payload, dict) else None
    if not isinstance(verify_path_value, str) or not verify_path_value.strip():
        return None
    candidate = Path(verify_path_value)
    if candidate.exists():
        return candidate
    if not candidate.is_absolute():
        joined = out_dir / candidate
        if joined.exists():
            return joined
    return None


def _write_rollback_plan_skeleton(out_dir: Path, from_verify_report: Path) -> Path:
    plan = {
        "schema_version": "rollback_plan.v1",
        "mode": "skeleton",
        "from_verify_report": str(from_verify_report),
        "items": [],
    }
    path = out_dir / "rollback_plan_latest.json"
    path.write_text(
        json.dumps(plan, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def _emit_policy_bundle_latest(
    out_dir: Path,
    *,
    policy_id: str,
    policy_version: str = "v1",
    policy_params: dict | None = None,
) -> Path:
    repo_root = Path(__file__).resolve().parents[2]
    catalog_path = Path(__file__).resolve().parent / "chords" / "catalog_v1.json"
    chord_catalog_sha256 = sha256_file(catalog_path) if catalog_path.exists() else None
    verify_report_path = _resolve_verify_report_for_bundle(out_dir)
    rollback_plan_path: Path | None = None
    if verify_report_path is not None:
        rollback_plan_path = _write_rollback_plan_skeleton(out_dir, verify_report_path)
    bundle = build_policy_bundle(
        mk_version=MK_VERSION,
        policy_id=policy_id,
        policy_version=policy_version,
        policy_params=policy_params or {},
        git_commit=_try_git_commit(repo_root),
        git_dirty=_try_git_dirty(repo_root),
        host=socket.gethostname() or None,
        passport_id=None,
        passport_sha256=None,
        chord_catalog_sha256=chord_catalog_sha256,
        rollback_from_verify_report=(str(verify_report_path) if verify_report_path else None),
        rollback_plan_path=(str(rollback_plan_path) if rollback_plan_path else None),
    )
    return write_policy_bundle(out_dir, bundle)


def _write_closed_loop_summary(
    out_dir: Path,
    report: dict,
    proposed: list[object],
    results: list[object],
) -> None:
    apply_requested = bool(report.get("apply_requested"))
    lines = [
        f"started_at: {report.get('started_at')}",
        f"finished_at: {report.get('finished_at')}",
        f"duration_s: {report.get('duration_s')}",
        f"mode: {report.get('mode')}",
        f"policy: {report.get('policy')}",
        f"apply_requested: {apply_requested}",
        f"dry_run: {report.get('dry_run')}",
        f"kill_switch_active: {report.get('kill_switch_active')}",
        f"kill_switch_signal: {report.get('kill_switch_signal')}",
        f"paid_enabled: {report.get('paid_enabled')}",
        f"verify_ok: {report.get('verify_ok')}",
        f"apply_decision_summary: {report.get('apply_decision_summary')}",
        f"apply_blocked_reason: {report.get('apply_blocked_reason')}",
        f"opportunity_hours_est: {report.get('opportunity_hours_est')}",
        f"opportunity_tokens_est: {report.get('opportunity_tokens_est')}",
        f"opportunity_usd_est: {report.get('opportunity_usd_est')}",
        f"opportunity_assumptions: {json.dumps(report.get('opportunity_assumptions') or {}, separators=(',', ':'), sort_keys=True)}",
        f"k8s_plan_path: {report.get('k8s_plan_path')}",
        f"k8s_plan_items: {report.get('k8s_plan_items')}",
        f"k8s_kubectl_plan_path: {report.get('k8s_kubectl_plan_path')}",
        f"k8s_namespace: {report.get('k8s_namespace')}",
        f"k8s_deployment: {report.get('k8s_deployment')}",
        f"k8s_verify_report_path: {report.get('k8s_verify_report_path')}",
        f"k8s_apply_report_path: {report.get('k8s_apply_report_path')}",
    ]
    if report.get("verify_ok") is False:
        lines.append(f"verify_blocker_kind: {report.get('verify_blocker_kind')}")
        verify_rbac_hint = report.get("verify_rbac_hint")
        if isinstance(verify_rbac_hint, str) and verify_rbac_hint.strip():
            lines.append(f"verify_rbac_hint: {verify_rbac_hint}")
    if apply_requested:
        apply_attempted = bool(report.get("apply_attempted"))
        apply_ok = report.get("apply_ok")
        if not apply_attempted:
            apply_ok_display = "n/a"
        elif apply_ok is True:
            apply_ok_display = "True"
        else:
            apply_ok_display = "False"
        proposed_n = len(proposed)
        results_n = len(results)
        lines.extend(
            [
                f"apply_attempted: {apply_attempted}",
                f"apply_ok: {apply_ok_display}",
                f"proposed_n: {proposed_n}",
                f"results_n: {results_n}",
                f"results_eq_proposed: {results_n == proposed_n}",
                f"blocked_reasons: {json.dumps(report.get('blocked_reasons') or {}, separators=(',', ':'), sort_keys=True)}",
                f"applied_reasons: {json.dumps(report.get('applied_reasons') or {}, separators=(',', ':'), sort_keys=True)}",
            ]
        )

    lines.append("proposed:")
    if proposed:
        for action in proposed:
            knob = getattr(action, "knob", None)
            target = getattr(action, "target", None)
            lines.append(f"- {knob} -> {target}")
    else:
        lines.append("- (none)")

    lines.append("applied:")
    if results:
        for result in results:
            if isinstance(result, dict):
                action = result.get("action")
                applied = result.get("applied")
                blocked = result.get("blocked")
                reason = result.get("reason")
            else:
                action = getattr(result, "action", None)
                applied = getattr(result, "applied", None)
                blocked = getattr(result, "blocked", None)
                reason = getattr(result, "reason", None)
            if isinstance(action, dict):
                knob = action.get("knob")
                target = action.get("target")
            else:
                knob = getattr(action, "knob", None)
                target = getattr(action, "target", None)
            lines.append(
                f"- {knob} -> {target} | applied={applied} blocked={blocked} reason={reason}"
            )
    else:
        lines.append("- (k8s apply pipeline; see k8s_apply_report_path)")

    summary_path = out_dir / "summary.md"
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _read_k8s_plan_best_effort(plan_path: Path) -> tuple[list[dict], str, str]:
    try:
        payload = json.loads(plan_path.read_text(encoding="utf-8"))
    except Exception:
        return [], "mixed", "mixed"
    items, _legacy_single_object, shape_error = _extract_k8s_plan_items(payload, command="k8s apply")
    if shape_error or items is None:
        return [], "mixed", "mixed"
    normalized, validation_error, _error_index = _validate_k8s_plan(items)
    if validation_error:
        return [], "mixed", "mixed"
    return (
        normalized,
        _infer_uniform_value(normalized, "namespace"),
        _infer_uniform_value(normalized, "name"),
    )


def _write_pro_required_k8s_apply_artifacts(
    *,
    out_dir: Path,
    plan_path: Path,
    block_reason: str = _PRO_REQUIRED_REASON,
    block_details: dict | None = None,
) -> Path:
    explain = ExplainLog(out_dir / "explain.jsonl")
    explain.emit(
        "k8s_apply_start",
        {"plan": str(plan_path), "out": str(out_dir), "force": False},
    )
    normalized_plan, namespace, deployment = _read_k8s_plan_best_effort(plan_path)
    details = {"feature": "k8s apply"}
    if isinstance(block_details, dict):
        details.update(block_details)
    explain.emit("k8s_apply_blocked", {"reason": block_reason, "details": details})

    started_at = _utc_now()
    finished_at = _utc_now()
    report_base = {
        "mode": "apply_skeleton",
        "k8s_plan_path": str(plan_path),
        "k8s_plan_items": len(normalized_plan),
        "k8s_namespace": namespace,
        "k8s_deployment": deployment,
        "objects": _k8s_objects_from_plan(normalized_plan),
        "paid_enabled": False,
        "would_apply": False,
        "block_reason": block_reason,
        "reason": block_reason,
        "ok": False,
        "items": [
            {
                **item,
                "object": _k8s_object(item["namespace"], item["name"]),
            }
            for item in normalized_plan
        ],
    }
    if isinstance(block_details, dict):
        if "kill_switch_active" in block_details:
            report_base["kill_switch_active"] = bool(block_details.get("kill_switch_active"))
        if "kill_switch_signal" in block_details:
            report_base["kill_switch_signal"] = block_details.get("kill_switch_signal")
    report = _build_report(
        report_base,
        started_at=started_at,
        finished_at=finished_at,
        out_dir=out_dir,
        mode="apply_skeleton",
        apply_requested=True,
        dry_run=True,
    )
    report_path = _write_report(
        out_dir,
        report,
        prefix="k8s_apply",
        latest_name="k8s_apply_latest.json",
    )
    explain.emit("k8s_apply_report", {"path": str(report_path)})
    return report_path


def _run_closed_loop_pro_required(
    args: argparse.Namespace,
    *,
    block_reason: str = _PRO_REQUIRED_REASON,
    kill_switch_active: bool = False,
    kill_switch_signal: str | None = None,
) -> int:
    observe_duration_ms = _parse_duration_ms(args.observe_duration)
    out_dir = Path(args.out)
    report, _ = _run_closed_loop_once(
        scenario=args.scenario,
        k8s_namespace=args.k8s_namespace,
        k8s_deployment=args.k8s_deployment,
        out_dir=out_dir,
        apply_requested=False,
        observe_source=args.observe_source,
        observe_path=Path(args.observe_path) if args.observe_path else None,
        observe_record_raw_path=Path(args.observe_record_raw)
        if args.observe_record_raw
        else None,
        observe_record_raw_mode="w",
        observe_duration_ms=observe_duration_ms,
        observe_container=args.observe_container,
        license_path=_resolve_license_path(getattr(args, "license_path", None)),
        policy=args.policy,
        cooldown_s=int(args.cooldown_s),
        approve_advanced=bool(args.approve_advanced),
        max_delta_per_step=int(args.max_delta_per_step),
        tick=0,
    )
    out_dir = _ensure_out_dir(args.out)
    proposed = report.get("proposed")
    if not isinstance(proposed, list):
        proposed = []
    results = [
        {
            "action": action,
            "applied": False,
            "blocked": True,
            "reason": block_reason,
            "dry_run": True,
        }
        for action in proposed
        if isinstance(action, dict)
    ]
    k8s_apply_report_path = _write_pro_required_k8s_apply_artifacts(
        out_dir=out_dir,
        plan_path=Path(str(report.get("k8s_plan_path") or out_dir / "k8s_plan.json")),
        block_reason=block_reason,
        block_details={
            "kill_switch_active": bool(kill_switch_active),
            "kill_switch_signal": kill_switch_signal,
        },
    )
    report["apply_requested"] = True
    report["dry_run"] = False
    report["apply_attempted"] = False
    report["apply_ok"] = None
    report["k8s_apply_rc"] = 2
    report["kill_switch_active"] = bool(kill_switch_active)
    report["kill_switch_signal"] = kill_switch_signal
    report["apply_blocked_reason"] = block_reason
    report["apply_decision_summary"] = f"apply blocked: {block_reason}"
    report["results"] = results
    report["blocked_reasons"] = {block_reason: len(results)} if results else {}
    report["applied_reasons"] = {}
    report["k8s_apply_report_path"] = str(k8s_apply_report_path)
    trace_path = out_dir / "decision_trace_latest.jsonl"
    if trace_path.exists():
        try:
            trace_lines = [line for line in trace_path.read_text(encoding="utf-8").splitlines() if line.strip()]
            if trace_lines:
                last_event = json.loads(trace_lines[-1])
                if isinstance(last_event, dict):
                    results_payload = last_event.get("results")
                    if not isinstance(results_payload, dict):
                        results_payload = {}
                    results_payload.update(
                        {
                            "apply_requested": True,
                            "dry_run": False,
                            "apply_attempted": False,
                            "apply_ok": None,
                            "blocked_reason": block_reason,
                            "apply_blocked_reason": block_reason,
                            "kill_switch_active": bool(kill_switch_active),
                            "kill_switch_signal": kill_switch_signal,
                        }
                    )
                    last_event["results"] = results_payload
                    trace_lines[-1] = json.dumps(
                        last_event,
                        sort_keys=True,
                        separators=(",", ":"),
                        ensure_ascii=False,
                    )
                    trace_path.write_text("\n".join(trace_lines) + "\n", encoding="utf-8")
        except Exception:
            pass
    explain = ExplainLog(out_dir / "explain.jsonl")
    explain.emit(
        "closed_loop_apply_blocked",
        {
            "reason": block_reason,
            "feature": "closed-loop --apply",
            "kill_switch_active": bool(kill_switch_active),
            "kill_switch_signal": kill_switch_signal,
        },
    )
    explain.emit(
        "closed_loop_apply_result",
        {
            "dry_run": False,
            "apply_requested": True,
            "apply_attempted": False,
            "apply_ok": None,
            "verify_ok": None,
            "blocked_reason": block_reason,
            "apply_blocked_reason": block_reason,
            "kill_switch_active": bool(kill_switch_active),
            "kill_switch_signal": kill_switch_signal,
            "k8s_verify_report_path": report.get("k8s_verify_report_path"),
            "k8s_apply_report_path": str(k8s_apply_report_path),
            "k8s_apply_rc": 2,
        },
    )
    _write_closed_loop_summary(out_dir, report, proposed, results)
    _write_report(
        out_dir,
        report,
        prefix="closed_loop",
        latest_name="closed_loop_latest.json",
    )
    if block_reason == _KILL_SWITCH_BLOCK_REASON:
        _emit_kill_switch_error()
        return 2
    return _require_pro("closed-loop --apply")


def _write_watch_pro_required_artifacts(
    base_out_dir: Path,
    interval_s: int | float,
    max_iterations: int | None,
    *,
    block_reason: str = _PRO_REQUIRED_REASON,
) -> None:
    started_at = _utc_now()
    report = _build_watch_report(
        base_out_dir=base_out_dir,
        started_at=started_at,
        finished_at=_utc_now(),
        interval_s=interval_s,
        max_iterations=max_iterations,
        iterations_done=0,
        last_iteration_out_dir=None,
        totals={
            "proposed_total": 0,
            "applied_total": 0,
            "blocked_total": 0,
            "verify_failed_total": 0,
            "apply_attempted_total": 0,
            "apply_ok_total": 0,
            "apply_failed_total": 0,
            "dry_run_total": 0,
        },
        observe_ingest_totals=None,
        observe_record_raw_path=None,
        observe_record_raw_lines_total=None,
    )
    report["apply_blocked_reason"] = block_reason
    _write_watch_latest(base_out_dir, report)
    _write_watch_summary(base_out_dir, report)


def _stable_action_sort_key(action: object) -> tuple[str, str, str, str]:
    knob = getattr(action, "knob", "")
    target = getattr(action, "target", "")
    reason = getattr(action, "reason", "")
    chord = getattr(action, "chord", "")
    return (
        str(knob),
        str(target),
        str(reason),
        str(chord) if chord is not None else "",
    )


def _stable_actions_to_dicts(actions: list[object]) -> tuple[list[object], list[dict]]:
    sorted_actions = sorted(actions, key=_stable_action_sort_key)
    payload: list[dict] = []
    for action in sorted_actions:
        item = {
            "knob": str(getattr(action, "knob", "")),
            "target": getattr(action, "target", None),
            "reason": str(getattr(action, "reason", "")),
        }
        chord = getattr(action, "chord", None)
        if chord is not None:
            item["chord"] = str(chord)
        payload.append(item)
    return sorted_actions, payload


def _format_bool_or_na(value: bool | None) -> str:
    if value is True:
        return "true"
    if value is False:
        return "false"
    return "n/a"


def _write_eval_summary(out_dir: Path, report: dict) -> Path:
    environment = report.get("environment")
    if not isinstance(environment, dict):
        environment = {}
    artifacts = report.get("artifacts")
    if not isinstance(artifacts, dict):
        artifacts = {}
    key_artifacts = report.get("key_artifacts")
    if not isinstance(key_artifacts, list):
        key_artifacts = []

    lines = [
        f"started_at: {report.get('started_at')}",
        f"finished_at: {report.get('finished_at')}",
        f"duration_s: {report.get('duration_s')}",
        f"source: {report.get('source')}",
        f"read_only: {report.get('read_only')}",
        f"verify_ok: {_format_bool_or_na(report.get('verify_ok'))}",
        f"top_blocker: {report.get('top_blocker') or 'n/a'}",
        f"environment.unstable: {bool(environment.get('unstable'))}",
        f"environment.nodes_seen: {json.dumps(environment.get('nodes_seen') or [], separators=(',', ':'), ensure_ascii=False)}",
        f"environment.gpu_models_seen: {json.dumps(environment.get('gpu_models_seen') or [], separators=(',', ':'), ensure_ascii=False)}",
        f"sample_count: {report.get('sample_count')}",
        f"proposed_actions_count: {report.get('proposed_actions_count')}",
        "key_artifacts:",
    ]
    for path in key_artifacts:
        lines.append(f"- {path}")
    if not key_artifacts:
        lines.append("- (none)")

    for key in sorted(artifacts):
        lines.append(f"artifact.{key}: {artifacts.get(key)}")

    summary_path = out_dir / "eval_summary.md"
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return summary_path


def _snip_text(text: str, *, max_lines: int = 12, max_chars: int = 500) -> str:
    value = (text or "").strip()
    if not value:
        return ""
    lines = value.splitlines()
    clipped_by_lines = False
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        clipped_by_lines = True
    clipped = "\n".join(lines)
    clipped_by_chars = False
    if len(clipped) > max_chars:
        clipped = clipped[: max_chars - 3] + "..."
        clipped_by_chars = True
    if clipped_by_lines or clipped_by_chars:
        return clipped + "\n...(truncated)"
    return clipped


def _parse_nonnegative_int(value: object) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value if value >= 0 else 0
    if isinstance(value, float):
        if value < 0:
            return 0
        return int(value)
    if isinstance(value, str):
        text = value.strip()
        if text.isdigit():
            return int(text)
    return 0


def _name_lines_contain(stdout: str, needle: str) -> bool:
    needle_l = needle.lower()
    for raw in (stdout or "").splitlines():
        line = raw.strip().lower()
        if line and needle_l in line:
            return True
    return False


def _write_k8s_preflight_summary(out_dir: Path, report: dict) -> Path:
    checks = report.get("checks")
    if not isinstance(checks, list):
        checks = []
    notes = report.get("notes")
    if not isinstance(notes, list):
        notes = []
    top_blocker = report.get("top_blocker")
    lines = [
        f"schema_version: {report.get('schema_version')}",
        f"started_at: {report.get('started_at')}",
        f"finished_at: {report.get('finished_at')}",
        f"duration_s: {report.get('duration_s')}",
        f"ok: {report.get('ok')}",
        f"top_blocker: {top_blocker if top_blocker else 'n/a'}",
        f"k8s_context: {report.get('k8s_context') or 'n/a'}",
        f"k8s_namespace: {report.get('k8s_namespace')}",
        f"k8s_deployment: {report.get('k8s_deployment')}",
        f"gpu_capacity_present: {bool(report.get('gpu_capacity_present'))}",
        f"nvidia_device_plugin_present: {bool(report.get('nvidia_device_plugin_present'))}",
        f"deploy_gpu_request: {_parse_nonnegative_int(report.get('deploy_gpu_request'))}",
        f"notes: {json.dumps([item for item in notes if isinstance(item, str)], separators=(',', ':'))}",
        "",
        "checks:",
    ]
    for check in checks:
        name = check.get("name")
        ok = check.get("ok")
        rc = check.get("rc")
        lines.append(f"- {name}: ok={ok} rc={rc}")
    summary_path = out_dir / "preflight_summary.md"
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return summary_path


def cmd_k8s_preflight(args: argparse.Namespace) -> int:
    out_dir = _ensure_out_dir(args.out)
    explain = ExplainLog(out_dir / "explain.jsonl")
    started_at = _utc_now()
    namespace = str(args.k8s_namespace)
    deployment = str(args.k8s_deployment)
    explain.emit(
        "k8s_preflight_start",
        {"out": str(out_dir), "k8s_namespace": namespace, "k8s_deployment": deployment},
    )

    check_specs = [
        ("current_context", ["config", "current-context"], 4, 240),
        ("cluster_info", ["cluster-info"], 8, 500),
        ("get_ns", ["get", "ns"], 12, 500),
        ("get_deployment_wide", ["-n", namespace, "get", "deploy", deployment, "-o", "wide"], 8, 500),
        ("get_pods_wide", ["-n", namespace, "get", "pods", "-o", "wide"], 8, 500),
        ("can_i_get_pods", ["auth", "can-i", "get", "pods", "-n", namespace], 4, 120),
        ("can_i_get_deployments_apps", ["auth", "can-i", "get", "deployments.apps", "-n", namespace], 4, 120),
    ]

    checks: list[dict] = []
    context: str | None = None
    for name, kubectl_args, max_lines, max_chars in check_specs:
        explain.emit("k8s_preflight_check_start", {"name": name, "args": kubectl_args})
        res = _kubectl(kubectl_args)
        stdout_snip = _snip_text(res.get("stdout") or "", max_lines=max_lines, max_chars=max_chars)
        stderr_snip = _snip_text(res.get("stderr") or "", max_lines=4, max_chars=240)
        rc = res.get("rc")
        ok = bool(rc == 0)
        if name == "current_context" and ok and stdout_snip:
            context = (res.get("stdout") or "").strip().splitlines()[0].strip()
        checks.append(
            {
                "name": name,
                "ok": ok,
                "rc": rc,
                "stdout_snip": stdout_snip,
                "stderr_snip": stderr_snip,
            }
        )
        explain.emit("k8s_preflight_check_result", {"name": name, "ok": ok, "rc": rc})

    ok = all(check.get("ok") is True for check in checks)
    top_blocker: str | None = None
    if not ok:
        failed = next((check for check in checks if check.get("ok") is not True), None)
        if failed is not None:
            name = str(failed.get("name") or "unknown")
            stderr_snip = str(failed.get("stderr_snip") or "")
            if "No such file or directory" in stderr_snip and "kubectl" in stderr_snip:
                top_blocker = "kubectl_not_found"
            else:
                top_blocker = f"{name} failed"

    gpu_capacity_present = False
    nvidia_device_plugin_present = False
    deploy_gpu_request = 0

    nodes_json = _kubectl(["get", "nodes", "-o", "json"])
    if nodes_json.get("rc") == 0:
        try:
            payload = json.loads(nodes_json.get("stdout") or "{}")
        except Exception:
            payload = {}
        if isinstance(payload, dict):
            for node in payload.get("items") or []:
                if not isinstance(node, dict):
                    continue
                status = node.get("status")
                if not isinstance(status, dict):
                    continue
                capacity = status.get("capacity")
                allocatable = status.get("allocatable")
                has_capacity = isinstance(capacity, dict) and "nvidia.com/gpu" in capacity
                has_allocatable = isinstance(allocatable, dict) and "nvidia.com/gpu" in allocatable
                if has_capacity or has_allocatable:
                    gpu_capacity_present = True
                    break

    ds_names = _kubectl(["-n", "kube-system", "get", "ds", "-o", "name"])
    pod_names = _kubectl(["-n", "kube-system", "get", "pods", "-o", "name"])
    nvidia_device_plugin_present = _name_lines_contain(
        ds_names.get("stdout") or "",
        "nvidia-device-plugin",
    ) or _name_lines_contain(
        pod_names.get("stdout") or "",
        "nvidia-device-plugin",
    )

    deploy_json = _kubectl(["-n", namespace, "get", "deploy", deployment, "-o", "json"])
    if deploy_json.get("rc") == 0:
        try:
            payload = json.loads(deploy_json.get("stdout") or "{}")
        except Exception:
            payload = {}
        containers = (
            ((payload.get("spec") or {}).get("template") or {}).get("spec") or {}
        ).get("containers")
        if isinstance(containers, list):
            for container in containers:
                if not isinstance(container, dict):
                    continue
                resources = container.get("resources")
                if not isinstance(resources, dict):
                    continue
                limits = resources.get("limits")
                requests = resources.get("requests")
                if isinstance(limits, dict):
                    deploy_gpu_request += _parse_nonnegative_int(limits.get("nvidia.com/gpu"))
                if isinstance(requests, dict):
                    deploy_gpu_request += _parse_nonnegative_int(requests.get("nvidia.com/gpu"))

    notes: list[str] = []
    if not gpu_capacity_present:
        notes.append("gpu_not_in_cluster")
    if not nvidia_device_plugin_present:
        notes.append("device_plugin_missing")
    if deploy_gpu_request <= 0:
        notes.append("deploy_not_requesting_gpu")

    finished_at = _utc_now()
    preflight_path = out_dir / "preflight_latest.json"
    report = {
        "schema_version": "preflight.v0",
        "started_at": _format_utc(started_at),
        "finished_at": _format_utc(finished_at),
        "duration_s": int((finished_at - started_at).total_seconds()),
        "ok": bool(ok),
        "top_blocker": top_blocker,
        "k8s_context": context,
        "k8s_namespace": namespace,
        "k8s_deployment": deployment,
        "gpu_capacity_present": gpu_capacity_present,
        "nvidia_device_plugin_present": nvidia_device_plugin_present,
        "deploy_gpu_request": deploy_gpu_request,
        "notes": notes,
        "checks": checks,
        "key_artifacts": [],
    }

    summary_path = _write_k8s_preflight_summary(out_dir, report)
    artifacts = [
        str(preflight_path),
        str(summary_path),
        str(out_dir / "explain.jsonl"),
    ]
    report["key_artifacts"] = artifacts
    preflight_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    explain.emit("k8s_preflight_report", {"path": str(preflight_path), "summary_path": str(summary_path), "ok": ok})
    print(
        " ".join(
            [
                f"ok={'true' if ok else 'false'}",
                f"top_blocker={top_blocker or 'n/a'}",
                f"context={context or 'n/a'}",
                f"ns={namespace}",
                f"deploy={deployment}",
                f"preflight={preflight_path}",
                f"summary={summary_path}",
                f"gpu_capacity_present={'true' if gpu_capacity_present else 'false'}",
                f"device_plugin_present={'true' if nvidia_device_plugin_present else 'false'}",
                f"deploy_gpu_request={deploy_gpu_request}",
            ]
        )
    )
    return 0 if ok else 1


def _run_eval(
    *,
    out_dir: Path,
    observe_source: str,
    observe_path: Path | None,
    observe_duration_ms: int,
    k8s_namespace: str,
    k8s_deployment: str,
    observe_container: str,
    policy: str,
) -> int:
    started_at = _utc_now()
    out_dir = _ensure_out_dir(out_dir)
    explain = ExplainLog(out_dir / "explain.jsonl")
    explain.emit(
        "eval_start",
        {
            "source": observe_source,
            "out": str(out_dir),
            "duration_ms": observe_duration_ms,
            "policy": policy,
        },
    )

    samples, source = _collect_observe_samples(
        scenario="drift",
        observe_source=observe_source,
        observe_path=observe_path,
        k8s_namespace=k8s_namespace,
        k8s_deployment=k8s_deployment,
        observe_container=observe_container,
        observe_duration_ms=observe_duration_ms,
        observe_record_raw_path=None,
        observe_record_raw_mode="w",
        required_path_flag="--path",
        required_source_flag="--source",
    )
    signals = analyze_signals(samples)
    proposed = propose_actions(
        signals,
        policy=policy,
        registry=_build_registry(),
    )
    sorted_proposed, proposed_actions = _stable_actions_to_dicts(proposed)

    explain.emit(
        "eval_signals",
        {"sample_count": len(samples), "signals": signals, "proposed_actions_count": len(proposed_actions)},
    )

    verify_ok: bool | None = None
    top_blocker: str | None = None
    k8s_plan_path: Path | None = None
    k8s_kubectl_plan_path: Path | None = None
    k8s_verify_report_path: Path | None = None

    if observe_source in ("k8s", "k8s-logs"):
        k8s_plan = build_k8s_plan(
            sorted_proposed,
            namespace=k8s_namespace,
            deployment=k8s_deployment,
        )
        k8s_plan = sorted(
            k8s_plan,
            key=lambda item: (
                str(item.get("namespace", "")),
                str(item.get("name", "")),
                json.dumps(item.get("patch") or {}, separators=(",", ":"), sort_keys=True),
            ),
        )
        k8s_plan_path = out_dir / "k8s_plan.json"
        k8s_plan_path.write_text(
            json.dumps(k8s_plan, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        k8s_kubectl_plan_path = _write_kubectl_plan(
            out_dir,
            k8s_plan,
            namespace=k8s_namespace,
            deployment=k8s_deployment,
        )
        explain.emit(
            "eval_plan_written",
            {
                "k8s_plan_path": str(k8s_plan_path),
                "k8s_kubectl_plan_path": str(k8s_kubectl_plan_path),
                "k8s_plan_items": len(k8s_plan),
            },
        )

        verify_rc, verify_path, verify_report = _run_k8s_verify(
            k8s_plan_path,
            out_dir,
            explain,
        )
        if verify_rc == 0 and isinstance(verify_report, dict):
            verify_ok = bool(verify_report.get("ok") is True)
            blocker = verify_report.get("verify_blocker")
            if isinstance(blocker, dict):
                kind = blocker.get("kind")
                if isinstance(kind, str) and kind.strip():
                    top_blocker = kind.strip()
            if verify_ok is True:
                top_blocker = None
            elif top_blocker is None:
                top_blocker = "unknown"
            k8s_verify_report_path = verify_path
        else:
            verify_ok = False
            top_blocker = "verify_error"

    finished_at = _utc_now()
    eval_latest_path = out_dir / "eval_latest.json"
    eval_summary_path = out_dir / "eval_summary.md"
    artifacts: dict[str, str] = {
        "eval_latest_path": str(eval_latest_path),
        "eval_summary_path": str(eval_summary_path),
        "explain_path": str(out_dir / "explain.jsonl"),
    }
    if observe_path is not None:
        artifacts["observe_input_path"] = str(observe_path)
    if k8s_plan_path is not None:
        artifacts["k8s_plan_path"] = str(k8s_plan_path)
    if k8s_kubectl_plan_path is not None:
        artifacts["k8s_kubectl_plan_path"] = str(k8s_kubectl_plan_path)
    if k8s_verify_report_path is not None:
        artifacts["k8s_verify_report_path"] = str(k8s_verify_report_path)
    key_artifacts = sorted(path for path in artifacts.values() if isinstance(path, str) and path)

    report = {
        "schema_version": "eval.v0",
        "started_at": _format_utc(started_at),
        "finished_at": _format_utc(finished_at),
        "duration_s": int((finished_at - started_at).total_seconds()),
        "out_dir": str(out_dir),
        "source": observe_source,
        "policy": policy,
        "read_only": True,
        "apply_requested": False,
        "dry_run": True,
        "sample_count": len(samples),
        "telemetry_points_included": _has_loss_and_throughput(samples),
        "signals": signals,
        "environment": _build_environment_fingerprint(samples),
        "proposed_actions_count": len(proposed_actions),
        "proposed_actions": proposed_actions,
        "verify_ok": verify_ok,
        "top_blocker": top_blocker,
        "artifacts": artifacts,
        "key_artifacts": key_artifacts,
    }
    if observe_source == "file":
        report["observe_path"] = str(observe_path) if observe_path else None
        report["observe_ingest"] = getattr(source, "observe_ingest", None)
    if observe_source in ("k8s", "k8s-logs"):
        report["k8s_namespace"] = k8s_namespace
        report["k8s_deployment"] = k8s_deployment
        report["k8s_plan_items"] = len(proposed_actions)
        report["k8s_verify_report_path"] = str(k8s_verify_report_path) if k8s_verify_report_path else None

    eval_latest_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    summary_path = _write_eval_summary(out_dir, report)
    explain.emit("eval_report", {"path": str(eval_latest_path), "summary_path": str(summary_path)})

    print(
        " ".join(
            [
                f"verify_ok={_format_bool_or_na(verify_ok)}",
                f"top_blocker={top_blocker or 'n/a'}",
                f"unstable={bool(report['environment'].get('unstable'))}",
                f"nodes_seen={len(report['environment'].get('nodes_seen') or [])}",
                f"gpu_models_seen={len(report['environment'].get('gpu_models_seen') or [])}",
                f"sample_count={len(samples)}",
                f"proposed_actions_count={len(proposed_actions)}",
                f"eval={eval_latest_path}",
                f"summary={summary_path}",
            ]
        )
    )
    return 0


def _build_registry() -> ActuatorRegistry:
    registry = ActuatorRegistry()
    registry.register(Knob("dataloader_num_workers", 1, 16, step=1, value=4))
    registry.register(Knob("dataloader_prefetch_factor", 1, 8, step=1, value=2))
    registry.register(Knob("grad_accum_steps", 1, 64, step=1, value=4))
    registry.register(Knob("microbatch_size", 1, 256, step=1, value=32))
    registry.register(Knob("comm_bucket_mb", 16, 512, step=16, value=128))
    registry.register(Knob("timeout_ms", 1000, 60000, step=500, value=5000))
    registry.register(Knob("concurrency", 1, 64, step=1, value=8))
    return registry


def _collect_observe_samples(
    *,
    scenario: str,
    observe_source: str,
    observe_path: Path | None,
    k8s_namespace: str,
    k8s_deployment: str,
    observe_container: str,
    observe_duration_ms: int,
    observe_record_raw_path: Path | None,
    observe_record_raw_mode: str,
    k8s_pod: str | None = None,
    required_path_flag: str = "--observe-path",
    required_source_flag: str = "--observe-source",
) -> tuple[list, object]:
    if observe_source == "file":
        if not observe_path:
            raise SystemExit(f"{required_path_flag} is required when {required_source_flag} file")
        source = FileSource(
            observe_path,
            record_raw_path=observe_record_raw_path,
            record_raw_mode=observe_record_raw_mode,
        )
    elif observe_source in ("k8s", "k8s-logs"):
        source = K8sLogSource(
            namespace=k8s_namespace,
            deployment=k8s_deployment,
            container=observe_container,
            k8s_pod=k8s_pod,
            duration_ms=observe_duration_ms,
            record_raw_path=observe_record_raw_path,
            record_raw_mode=observe_record_raw_mode,
        )
    else:
        source = SyntheticSource(scenario=scenario, duration_ms=observe_duration_ms)
    collector = TelemetryCollector(source)
    samples = collector.collect()
    return samples, source


def _collect_doctor_checks() -> tuple[list[dict], bool]:
    checks: list[dict] = []
    checks.append(
        {
            "label": "mk runnable",
            "ok": True,
            "hint": "",
        }
    )
    kubectl_override = str(os.environ.get("KUBECTL", "")).strip()
    kubectl_path = (
        shutil.which(kubectl_override) if kubectl_override else shutil.which("kubectl")
    )
    checks.append(
        {
            "label": "kubectl present",
            "ok": bool(kubectl_path),
            "hint": "Install kubectl and add it to PATH.",
        }
    )

    kubeconfig_raw = str(os.environ.get("KUBECONFIG", "")).strip()
    kubeconfig_path = (
        Path(kubeconfig_raw) if kubeconfig_raw else Path.home() / ".kube" / "config"
    )
    checks.append(
        {
            "label": f"kubeconfig readable ({kubeconfig_path})",
            "ok": kubeconfig_path.is_file() and os.access(kubeconfig_path, os.R_OK),
            "hint": "Set KUBECONFIG or ensure ~/.kube/config exists and is readable.",
        }
    )
    ok = all(bool(item.get("ok")) for item in checks)
    return checks, ok


def cmd_preflight(args: argparse.Namespace) -> int:
    out_dir = _ensure_out_dir(args.out)
    inputs_root = _resolve_inputs_root(out_dir, getattr(args, "inputs_root", None))
    started_at = _utc_now()
    plan_path, plan_report = _find_and_read_json(inputs_root, "closed_loop_latest.json")
    verify_path, verify_report = _find_and_read_json(inputs_root, "k8s_verify_latest.json")

    verify_ok = verify_report.get("ok") if isinstance(verify_report, dict) else None
    verify_blocker = verify_report.get("verify_blocker") if isinstance(verify_report, dict) else None
    top_blocker: str | None = None
    if isinstance(verify_blocker, dict):
        blocker_kind = verify_blocker.get("kind")
        if isinstance(blocker_kind, str) and blocker_kind.strip():
            top_blocker = blocker_kind.strip()
    if top_blocker is None and verify_ok is False:
        top_blocker = "verify_not_ok"

    notes: list[str] = []
    if plan_path is None:
        notes.append("missing_closed_loop_latest")
    elif plan_report is None:
        notes.append("invalid_closed_loop_latest")
    if verify_path is None:
        notes.append("missing_k8s_verify_latest")
    elif verify_report is None:
        notes.append("invalid_k8s_verify_latest")

    finished_at = _utc_now()
    report = {
        "schema_version": "preflight.v0",
        "started_at": _format_utc(started_at),
        "finished_at": _format_utc(finished_at),
        "duration_s": int((finished_at - started_at).total_seconds()),
        "read_only": True,
        "inputs_root": str(inputs_root),
        "ok": bool(verify_ok is True and top_blocker is None),
        "top_blocker": top_blocker,
        "notes": notes,
        "k8s_namespace": plan_report.get("k8s_namespace") if isinstance(plan_report, dict) else None,
        "k8s_deployment": plan_report.get("k8s_deployment") if isinstance(plan_report, dict) else None,
        "verify_ok": verify_ok,
        "verify_report_path": str(verify_path) if verify_path is not None else None,
        "plan_report_path": str(plan_path) if plan_path is not None else None,
        "key_artifacts": [],
    }
    summary_lines = [
        "# Preflight",
        f"ok: {_report_bool(bool(report['ok']))}",
        f"top_blocker: {top_blocker or 'n/a'}",
        f"inputs_root: {inputs_root}",
        f"verify_ok: {verify_ok}",
        f"notes: {json.dumps(notes, separators=(',', ':'), ensure_ascii=False)}",
    ]
    summary_text = "\n".join(summary_lines) + "\n"
    summary_path, legacy_summary_path = _write_summary_aliases(
        out_dir,
        legacy_name="preflight_summary.md",
        text=summary_text,
    )
    latest_path, ts_path = _write_latest_with_timestamp(
        out_dir,
        latest_name="preflight_latest.json",
        prefix="preflight",
        payload=report,
    )
    report["key_artifacts"] = [str(latest_path), str(ts_path), str(summary_path), str(legacy_summary_path)]
    _write_json_report(latest_path, report)
    _write_json_report(ts_path, report)
    return 0


def cmd_eval(args: argparse.Namespace) -> int:
    out_value = getattr(args, "out", None) or "report/eval"
    out_dir = _ensure_out_dir(out_value)
    inputs_root = _resolve_inputs_root(out_dir, getattr(args, "inputs_root", None))
    started_at = _utc_now()
    plan_path, plan_report = _find_and_read_json(inputs_root, "closed_loop_latest.json")
    verify_path, verify_report = _find_and_read_json(inputs_root, "k8s_verify_latest.json")
    notes: list[str] = []
    if plan_path is None:
        notes.append("missing_closed_loop_latest")
    elif plan_report is None:
        notes.append("invalid_closed_loop_latest")

    signals = plan_report.get("signals") if isinstance(plan_report, dict) else None
    if not isinstance(signals, dict):
        signals = {}
        notes.append("signals_missing")
    environment = plan_report.get("environment") if isinstance(plan_report, dict) else None
    if not isinstance(environment, dict):
        environment = {}
        notes.append("environment_missing")

    proposed = plan_report.get("proposed") if isinstance(plan_report, dict) else None
    proposed_actions_count = len(proposed) if isinstance(proposed, list) else 0
    verify_ok = verify_report.get("ok") if isinstance(verify_report, dict) else None
    top_blocker: str | None = None
    verify_blocker = verify_report.get("verify_blocker") if isinstance(verify_report, dict) else None
    if isinstance(verify_blocker, dict):
        kind = verify_blocker.get("kind")
        if isinstance(kind, str) and kind.strip():
            top_blocker = kind.strip()
    if top_blocker is None and verify_ok is False:
        top_blocker = "verify_not_ok"

    finished_at = _utc_now()
    report = {
        "schema_version": "eval.v0",
        "started_at": _format_utc(started_at),
        "finished_at": _format_utc(finished_at),
        "duration_s": int((finished_at - started_at).total_seconds()),
        "read_only": True,
        "inputs_root": str(inputs_root),
        "source": "inputs_root",
        "ok": bool(top_blocker is None and plan_report is not None),
        "verify_ok": verify_ok,
        "top_blocker": top_blocker,
        "sample_count": plan_report.get("sample_count") if isinstance(plan_report, dict) else None,
        "signals": signals,
        "environment": environment,
        "proposed_actions_count": proposed_actions_count,
        "notes": sorted(set(notes)),
        "artifacts": {
            "plan_report_path": str(plan_path) if plan_path is not None else None,
            "verify_report_path": str(verify_path) if verify_path is not None else None,
        },
        "key_artifacts": [],
    }
    summary_lines = [
        "# Eval",
        f"ok: {_report_bool(bool(report['ok']))}",
        f"top_blocker: {top_blocker or 'n/a'}",
        f"inputs_root: {inputs_root}",
        f"sample_count: {report.get('sample_count')}",
        f"proposed_actions_count: {proposed_actions_count}",
        f"notes: {json.dumps(report['notes'], separators=(',', ':'), ensure_ascii=False)}",
    ]
    summary_text = "\n".join(summary_lines) + "\n"
    summary_path, legacy_summary_path = _write_summary_aliases(
        out_dir,
        legacy_name="eval_summary.md",
        text=summary_text,
    )
    latest_path, ts_path = _write_latest_with_timestamp(
        out_dir,
        latest_name="eval_latest.json",
        prefix="eval",
        payload=report,
    )
    report["key_artifacts"] = [str(latest_path), str(ts_path), str(summary_path), str(legacy_summary_path)]
    _write_json_report(latest_path, report)
    _write_json_report(ts_path, report)
    return 0


def cmd_watch(args: argparse.Namespace) -> int:
    out_dir = _ensure_out_dir(args.out)
    inputs_root = _resolve_inputs_root(out_dir, getattr(args, "inputs_root", None))
    duration_s = int(getattr(args, "duration", 60))
    if duration_s < 1:
        duration_s = 1

    started_at = _utc_now()
    plan_path, plan_report = _find_and_read_json(inputs_root, "closed_loop_latest.json")
    notes: list[str] = []
    if plan_path is None:
        notes.append("missing_closed_loop_latest")
    elif plan_report is None:
        notes.append("invalid_closed_loop_latest")

    proposed = plan_report.get("proposed") if isinstance(plan_report, dict) else None
    proposed_total = len(proposed) if isinstance(proposed, list) else 0
    blocked_reasons = plan_report.get("blocked_reasons") if isinstance(plan_report, dict) else None
    blocked_total = sum(v for v in blocked_reasons.values() if isinstance(v, int)) if isinstance(blocked_reasons, dict) else 0
    applied_reasons = plan_report.get("applied_reasons") if isinstance(plan_report, dict) else None
    applied_total = sum(v for v in applied_reasons.values() if isinstance(v, int)) if isinstance(applied_reasons, dict) else 0

    finished_at = _utc_now()
    report = {
        "schema_version": "v0",
        "started_at": _format_utc(started_at),
        "finished_at": _format_utc(finished_at),
        "duration_s": duration_s,
        "interval_s": duration_s,
        "max_iterations": 1,
        "iterations_done": 1 if plan_report is not None else 0,
        "last_iteration_out_dir": str(plan_path.parent) if plan_path is not None else None,
        "proposed_total": proposed_total,
        "blocked_total": blocked_total,
        "applied_total": applied_total,
        "verify_failed_total": 0,
        "apply_attempted_total": 0,
        "apply_ok_total": 0,
        "apply_failed_total": 0,
        "dry_run_total": 1 if plan_report is not None else 0,
        "read_only": True,
        "inputs_root": str(inputs_root),
        "ok": bool(plan_report is not None),
        "top_blocker": None if plan_report is not None else "missing_closed_loop_latest",
        "notes": sorted(set(notes)),
        "observe_ingest": plan_report.get("observe_ingest") if isinstance(plan_report, dict) else None,
        "observe_record_raw_path": None,
        "observe_record_raw_lines_written": None,
        "artifact_paths": {
            "watch_latest_path": str(out_dir / "watch_latest.json"),
            "watch_summary_path": str(out_dir / "watch_summary.md"),
            "last_iteration_report_path": str(plan_path) if plan_path is not None else None,
            "last_iteration_explain_path": str((plan_path.parent / "explain.jsonl")) if plan_path is not None else None,
        },
        "key_artifacts": [],
    }
    summary_lines = [
        "# Watch",
        f"ok: {_report_bool(bool(report['ok']))}",
        f"inputs_root: {inputs_root}",
        f"duration_s: {duration_s}",
        f"iterations_done: {report.get('iterations_done')}",
        f"proposed_total: {proposed_total}",
        f"blocked_total: {blocked_total}",
        f"applied_total: {applied_total}",
        f"notes: {json.dumps(report['notes'], separators=(',', ':'), ensure_ascii=False)}",
    ]
    summary_text = "\n".join(summary_lines) + "\n"
    summary_path, legacy_summary_path = _write_summary_aliases(
        out_dir,
        legacy_name="watch_summary.md",
        text=summary_text,
    )
    latest_path, ts_path = _write_latest_with_timestamp(
        out_dir,
        latest_name="watch_latest.json",
        prefix="watch",
        payload=report,
    )
    report["key_artifacts"] = [str(latest_path), str(ts_path), str(summary_path), str(legacy_summary_path)]
    _write_json_report(latest_path, report)
    _write_json_report(ts_path, report)
    return 0


def cmd_roi(args: argparse.Namespace) -> int:
    out_value = getattr(args, "out", None) or "report/roi"
    out_dir = _ensure_out_dir(out_value)
    inputs_root = _resolve_inputs_root(out_dir, getattr(args, "inputs_root", None))
    preflight_path = inputs_root / "preflight" / "preflight_latest.json"
    eval_path = inputs_root / "eval" / "eval_latest.json"
    watch_path = inputs_root / "watch" / "watch_latest.json"
    rc = cmd_roi_report(
        argparse.Namespace(
            preflight=str(preflight_path),
            eval=str(eval_path),
            watch=str(watch_path),
            out=str(out_dir),
        )
    )
    if rc != 0:
        return rc
    latest_path = out_dir / "roi_latest.json"
    summary_path = out_dir / "roi_summary.md"
    latest_payload, error = _read_json_best_effort(latest_path)
    if error or not isinstance(latest_payload, dict):
        return 2
    latest_payload["inputs_root"] = str(inputs_root)
    _write_json_report(latest_path, latest_payload)
    ts_path = out_dir / f"roi_{_report_ts()}.json"
    _write_json_report(ts_path, latest_payload)
    if summary_path.exists():
        (out_dir / "summary.md").write_text(summary_path.read_text(encoding="utf-8"), encoding="utf-8")
    key_artifacts = latest_payload.get("key_artifacts")
    if isinstance(key_artifacts, list):
        key_artifacts = [item for item in key_artifacts if isinstance(item, str)]
    else:
        key_artifacts = []
    for path in (str(ts_path), str(out_dir / "summary.md")):
        if path not in key_artifacts:
            key_artifacts.append(path)
    latest_payload["key_artifacts"] = sorted(set(key_artifacts))
    _write_json_report(latest_path, latest_payload)
    _write_json_report(ts_path, latest_payload)
    return 0


def cmd_doctor(_args: argparse.Namespace) -> int:
    checks, ok = _collect_doctor_checks()
    for check in checks:
        label = str(check.get("label") or "")
        hint = str(check.get("hint") or "")
        passed = bool(check.get("ok"))
        if passed:
            print(f"PASS {label}")
            continue
        print(f"FAIL {label}")
        print(f"  hint: {hint}")

    if not ok:
        print("Doctor result: FAIL")
        return 2
    print("Doctor result: PASS")
    return 0


def _write_quickstart_summary(
    out_dir: Path,
    *,
    doctor_report: dict,
    closed_loop_report: dict,
    verify_report: dict | None,
    export_out_dir: Path,
) -> Path:
    lines = [
        "# ModeKeeper Quickstart",
        f"doctor_ok: {_format_bool_or_na(doctor_report.get('ok'))}",
        f"apply_requested: {_format_bool_or_na(closed_loop_report.get('apply_requested'))}",
        f"dry_run: {_format_bool_or_na(closed_loop_report.get('dry_run'))}",
        f"kill_switch_active: {_format_bool_or_na(closed_loop_report.get('kill_switch_active'))}",
        f"paid_enabled: {_format_bool_or_na(closed_loop_report.get('paid_enabled'))}",
        f"license_ok: {_format_bool_or_na(closed_loop_report.get('license_ok'))}",
        f"verify_ok: {_format_bool_or_na((verify_report or {}).get('ok'))}",
        f"verify_blocker: {(verify_report or {}).get('verify_blocker') or 'n/a'}",
        "artifacts:",
        f"- doctor report: {out_dir / 'doctor' / 'doctor.json'}",
        f"- doctor summary: {out_dir / 'doctor' / 'summary.md'}",
        f"- plan report: {out_dir / 'plan' / 'closed_loop_latest.json'}",
        f"- verify report: {out_dir / 'verify' / 'k8s_verify_latest.json'}",
        f"- preflight report: {out_dir / 'preflight' / 'preflight_latest.json'}",
        f"- eval report: {out_dir / 'eval' / 'eval_latest.json'}",
        f"- watch report: {out_dir / 'watch' / 'watch_latest.json'}",
        f"- roi report: {out_dir / 'roi' / 'roi_latest.json'}",
        f"- export manifest: {export_out_dir / 'bundle_manifest.json'}",
        f"- export tar: {export_out_dir / 'bundle.tar.gz'}",
        f"- export summary: {export_out_dir / 'bundle_summary.md'}",
    ]
    summary_path = out_dir / "summary.md"
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return summary_path


def cmd_quickstart(args: argparse.Namespace) -> int:
    out_value = args.out
    if not isinstance(out_value, str) or not out_value.strip():
        out_value = str(Path("report") / f"quickstart_{_utc_now().strftime('%Y%m%dT%H%M%SZ')}")
    out_dir = _ensure_out_dir(out_value)

    doctor_out_dir = _ensure_out_dir(str(out_dir / "doctor"))
    doctor_started_at = _utc_now()
    doctor_checks, doctor_ok = _collect_doctor_checks()
    doctor_finished_at = _utc_now()
    doctor_report = {
        "schema_version": "doctor.v0",
        "started_at": _format_utc(doctor_started_at),
        "finished_at": _format_utc(doctor_finished_at),
        "duration_s": int((doctor_finished_at - doctor_started_at).total_seconds()),
        "ok": doctor_ok,
        "checks": doctor_checks,
    }
    (doctor_out_dir / "doctor.json").write_text(
        json.dumps(doctor_report, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    doctor_summary_lines = [
        "# Doctor",
        f"ok: {_format_bool_or_na(doctor_ok)}",
        "checks:",
    ]
    for check in doctor_checks:
        doctor_summary_lines.append(
            f"- {check.get('label')}: {_format_bool_or_na(check.get('ok'))}"
        )
    (doctor_out_dir / "summary.md").write_text(
        "\n".join(doctor_summary_lines) + "\n",
        encoding="utf-8",
    )

    observe_duration_ms = _parse_duration_ms(args.observe_duration)
    plan_out_dir = out_dir / "plan"
    _run_closed_loop_once(
        scenario=args.scenario,
        k8s_namespace=args.k8s_namespace,
        k8s_deployment=args.k8s_deployment,
        out_dir=plan_out_dir,
        apply_requested=False,
        observe_source=args.observe_source,
        observe_path=Path(args.observe_path) if args.observe_path else None,
        observe_record_raw_path=None,
        observe_record_raw_mode="w",
        observe_duration_ms=observe_duration_ms,
        observe_container=args.observe_container,
        license_path=None,
        policy=args.policy,
        cooldown_s=30,
        approve_advanced=False,
        max_delta_per_step=0,
        tick=0,
    )

    closed_loop_latest_path = plan_out_dir / "closed_loop_latest.json"
    try:
        closed_loop_report = json.loads(closed_loop_latest_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        print(
            f"ERROR: quickstart expected artifact missing: {closed_loop_latest_path}",
            file=sys.stderr,
        )
        return 2
    except json.JSONDecodeError as exc:
        print(
            f"ERROR: quickstart cannot parse closed-loop latest report: {exc}",
            file=sys.stderr,
        )
        return 2

    k8s_plan_path_raw = str(closed_loop_report.get("k8s_plan_path") or "").strip()
    if not k8s_plan_path_raw:
        print(
            "ERROR: quickstart closed-loop report does not contain k8s_plan_path",
            file=sys.stderr,
        )
        return 2
    k8s_plan_path = Path(k8s_plan_path_raw)
    if not k8s_plan_path.is_absolute():
        k8s_plan_path = (Path.cwd() / k8s_plan_path).resolve()

    verify_out_dir = _ensure_out_dir(str(out_dir / "verify"))
    verify_explain = ExplainLog(verify_out_dir / "explain.jsonl")
    verify_rc, _, verify_report = _run_k8s_verify(k8s_plan_path, verify_out_dir, verify_explain)
    if verify_rc != 0:
        return verify_rc

    eval_rc = cmd_eval(argparse.Namespace(out=str(out_dir / "eval"), inputs_root=str(out_dir)))
    if eval_rc != 0:
        return eval_rc
    preflight_rc = cmd_preflight(argparse.Namespace(out=str(out_dir / "preflight"), inputs_root=str(out_dir)))
    if preflight_rc != 0:
        return preflight_rc
    watch_rc = cmd_watch(
        argparse.Namespace(
            out=str(out_dir / "watch"),
            inputs_root=str(out_dir),
            duration=max(1, int(_duration_ms_to_seconds(observe_duration_ms))),
        )
    )
    if watch_rc != 0:
        return watch_rc
    roi_rc = cmd_roi(argparse.Namespace(out=str(out_dir / "roi"), inputs_root=str(out_dir)))
    if roi_rc != 0:
        return roi_rc

    export_out_dir = out_dir / "export"
    export_rc = cmd_export_bundle(
        argparse.Namespace(
            input_dir=str(out_dir),
            out=str(export_out_dir),
        )
    )
    if export_rc != 0:
        return export_rc

    _write_quickstart_summary(
        out_dir,
        doctor_report=doctor_report,
        closed_loop_report=closed_loop_report,
        verify_report=verify_report,
        export_out_dir=export_out_dir,
    )
    return 0


def cmd_observe(args: argparse.Namespace) -> int:
    started_at = _utc_now()
    duration_ms = _parse_duration_ms(args.duration)
    out_dir = _ensure_out_dir(args.out)
    explain = ExplainLog(out_dir / "explain.jsonl")

    explain.emit("observe_start", {"duration_ms": duration_ms, "out": str(out_dir)})

    sm = ModeStateMachine(Mode.OBSERVE_ONLY)
    record_raw_path = Path(args.record_raw) if args.record_raw else None
    record_raw_mode = "w"
    observe_path = Path(args.path) if args.path else None
    samples, source = _collect_observe_samples(
        scenario="baseline",
        observe_source=args.source,
        observe_path=observe_path,
        k8s_namespace=args.k8s_namespace,
        k8s_deployment=args.k8s_deployment,
        observe_container=args.container,
        k8s_pod=args.k8s_pod,
        observe_duration_ms=duration_ms,
        observe_record_raw_path=record_raw_path,
        observe_record_raw_mode=record_raw_mode,
        required_path_flag="--path",
        required_source_flag="--source",
    )
    record_raw_lines_written = getattr(source, "record_raw_lines_written", 0)
    record_raw_error = getattr(source, "record_raw_error", None)
    if record_raw_path is not None and record_raw_error is None and args.source == "synthetic":
        record_raw_error = "unsupported_source"
    record_raw_path_value = str(record_raw_path) if record_raw_path else None
    if args.source == "file":
        explain.emit(
            "observe_source",
            {
                "source": "file",
                "path": str(observe_path),
                "rows_read": source.rows_read,
                "observe_ingest": source.observe_ingest,
                "record_raw_path": record_raw_path_value,
                "record_raw_lines_written": record_raw_lines_written,
                "record_raw_error": record_raw_error,
            },
        )
    else:
        if args.source in ("k8s", "k8s-logs"):
            explain.emit(
                "observe_source",
                {
                    "source": "k8s",
                    "namespace": args.k8s_namespace,
                    "deployment": args.k8s_deployment,
                    "container": args.container,
                    "rows_read": source.rows_read,
                    "samples_parsed": source.samples_parsed,
                    "error": source.error,
                    "record_raw_path": record_raw_path_value,
                    "record_raw_lines_written": record_raw_lines_written,
                    "record_raw_error": record_raw_error,
                },
            )
        else:
            explain.emit(
                "observe_source",
                {
                    "source": "synthetic",
                    "path": None,
                    "rows_read": len(samples),
                    "record_raw_path": record_raw_path_value,
                    "record_raw_lines_written": record_raw_lines_written,
                    "record_raw_error": record_raw_error,
                },
            )
    signals = analyze_signals(samples)

    explain.emit(
        "observe_signals",
        {"mode": sm.mode.value, "signals": signals, "sample_count": len(samples)},
    )

    summary = summarize_observe(signals)
    explain.emit("observe_summary", {"summary": summary})

    report_base = {
        "mode": sm.mode.value,
        "signals": signals,
        "sample_count": len(samples),
        "telemetry": _build_telemetry_payload(samples),
        "environment": _build_environment_fingerprint(samples),
        "note": "OBSERVE_ONLY: no actions applied",
        "summary": summary,
    }
    finished_at = _utc_now()
    report = _build_report(
        report_base,
        started_at=started_at,
        finished_at=finished_at,
        out_dir=out_dir,
        mode=sm.mode.value,
        apply_requested=False,
        dry_run=True,
    )
    report_path = _write_report(
        out_dir,
        report,
        prefix="report",
        latest_name="observe_latest.json",
    )
    explain.emit("observe_report", {"path": str(report_path)})
    explain.emit("observe_stop", {"mode": sm.mode.value})
    return 0


def cmd_eval_file(args: argparse.Namespace) -> int:
    return _run_eval(
        out_dir=Path(args.out),
        observe_source="file",
        observe_path=Path(args.path),
        observe_duration_ms=0,
        k8s_namespace="default",
        k8s_deployment="trainer",
        observe_container="auto",
        policy=args.policy,
    )


def cmd_eval_k8s(args: argparse.Namespace) -> int:
    return _run_eval(
        out_dir=Path(args.out),
        observe_source="k8s",
        observe_path=None,
        observe_duration_ms=_parse_duration_ms(args.observe_duration),
        k8s_namespace=args.k8s_namespace,
        k8s_deployment=args.k8s_deployment,
        observe_container=args.container,
        policy=args.policy,
    )


def _run_closed_loop_once(
    *,
    scenario: str,
    k8s_namespace: str,
    k8s_deployment: str,
    out_dir: Path,
    apply_requested: bool,
    observe_source: str,
    observe_path: Path | None,
    observe_record_raw_path: Path | None,
    observe_record_raw_mode: str,
    observe_duration_ms: int,
    observe_container: str,
    license_path: Path | None,
    policy: str,
    cooldown_s: int,
    approve_advanced: bool = False,
    max_delta_per_step: int = 0,
    tick: int = 0,
) -> tuple[dict, Path]:
    started_at = _utc_now()
    out_dir = _ensure_out_dir(out_dir)
    explain = ExplainLog(out_dir / "explain.jsonl")

    sm = ModeStateMachine(Mode.CLOSED_LOOP)
    guardrails = Guardrails(
        registry=_build_registry(),
        explain=explain,
        min_interval_s=cooldown_s,
        max_delta_per_step=max_delta_per_step,
    )
    drift_k8s_mode_requested = (
        scenario == "drift"
        and observe_source == "synthetic"
        and _resolve_drift_k8s_mode(k8s_namespace, k8s_deployment)
    )
    drift_k8s_mode_active = False
    drift_k8s_triggered = False
    drift_k8s_observed_knobs: dict[str, int | None] | None = None
    samples, source = _collect_observe_samples(
        scenario=scenario,
        observe_source=observe_source,
        observe_path=observe_path,
        k8s_namespace=k8s_namespace,
        k8s_deployment=k8s_deployment,
        observe_container=observe_container,
        observe_duration_ms=observe_duration_ms,
        observe_record_raw_path=observe_record_raw_path,
        observe_record_raw_mode=observe_record_raw_mode,
        required_path_flag="--observe-path",
        required_source_flag="--observe-source",
    )
    signals = analyze_signals(samples)
    if drift_k8s_mode_requested:
        observed_knobs = _read_k8s_deployment_template_knobs(
            namespace=k8s_namespace,
            deployment=k8s_deployment,
        )
        if observed_knobs is not None:
            signals, drift_k8s_triggered = _build_k8s_drift_signal_from_knobs(observed_knobs)
            drift_k8s_observed_knobs = observed_knobs
            drift_k8s_mode_active = True
    explain.emit(
        "closed_loop_drift_observed_knobs",
        {
            "source": "k8s" if drift_k8s_mode_active else "synthetic",
            "k8s_mode_requested": drift_k8s_mode_requested,
            "k8s_mode_active": drift_k8s_mode_active,
            "k8s_drift_triggered": drift_k8s_triggered,
            "observed_knobs": drift_k8s_observed_knobs,
            "targets": _DRIFT_K8S_TARGETS,
            "namespace": k8s_namespace,
            "deployment": k8s_deployment,
        },
    )
    proposed = propose_actions(
        signals,
        policy=policy,
        registry=guardrails.registry,
    )
    if drift_k8s_mode_active and not drift_k8s_triggered:
        proposed = []
    cost_model = _get_cost_model()
    opportunity = estimate_opportunity(samples, signals, **_get_opportunity_cost_model())
    value_summary = build_value_summary(
        samples=samples,
        signals=signals,
        opportunity=opportunity,
        cost_model=cost_model,
    )
    record_raw_lines_written = getattr(source, "record_raw_lines_written", 0)
    record_raw_error = getattr(source, "record_raw_error", None)
    if observe_record_raw_path is not None and record_raw_error is None and observe_source == "synthetic":
        record_raw_error = "unsupported_source"
    record_raw_path_value = (
        str(observe_record_raw_path) if observe_record_raw_path else None
    )

    if drift_k8s_mode_active:
        explain.emit(
            "closed_loop_observe_source",
            {
                "source": "k8s",
                "namespace": k8s_namespace,
                "deployment": k8s_deployment,
                "observed_knobs": drift_k8s_observed_knobs,
                "k8s_drift_triggered": drift_k8s_triggered,
                "record_raw_path": record_raw_path_value,
                "record_raw_lines_written": record_raw_lines_written,
                "record_raw_error": record_raw_error,
            },
        )
    elif observe_source == "file":
        explain.emit(
            "closed_loop_observe_source",
            {
                "source": "file",
                "path": str(observe_path),
                "rows_read": source.rows_read,
                "observe_ingest": source.observe_ingest,
                "record_raw_path": record_raw_path_value,
                "record_raw_lines_written": record_raw_lines_written,
                "record_raw_error": record_raw_error,
            },
        )
    elif observe_source in ("k8s", "k8s-logs"):
        explain.emit(
            "closed_loop_observe_source",
            {
                "source": "k8s",
                "namespace": k8s_namespace,
                "deployment": k8s_deployment,
                "container": observe_container,
                "rows_read": source.rows_read,
                "samples_parsed": source.samples_parsed,
                "error": source.error,
                "record_raw_path": record_raw_path_value,
                "record_raw_lines_written": record_raw_lines_written,
                "record_raw_error": record_raw_error,
            },
        )
    else:
        explain.emit(
            "closed_loop_observe_source",
            {
                "source": "synthetic",
                "path": None,
                "rows_read": len(samples),
                "record_raw_path": record_raw_path_value,
                "record_raw_lines_written": record_raw_lines_written,
                "record_raw_error": record_raw_error,
            },
        )

    explain.emit(
        "closed_loop_signals",
        {"mode": sm.mode.value, "signals": signals, "sample_count": len(samples)},
    )
    explain.emit(
        "closed_loop_proposed",
        {"proposed": [p.to_dict() for p in proposed]},
    )
    approved_actions, approval_blocked = split_actions_by_approval(
        proposed,
        apply_changes=apply_requested,
        approve_advanced=approve_advanced,
        explain=explain,
    )
    executable_actions = approved_actions if apply_requested else proposed

    k8s_plan = build_k8s_plan(
        executable_actions,
        namespace=k8s_namespace,
        deployment=k8s_deployment,
    )
    k8s_plan_path = out_dir / "k8s_plan.json"
    k8s_plan_path.write_text(
        json.dumps(k8s_plan, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    explain.emit(
        "k8s_plan_written",
        {"path": str(k8s_plan_path), "items": len(k8s_plan)},
    )
    k8s_kubectl_plan_path = _write_kubectl_plan(
        out_dir,
        k8s_plan,
        k8s_namespace,
        k8s_deployment,
    )
    explain.emit(
        "k8s_kubectl_plan_written",
        {"path": str(k8s_kubectl_plan_path), "items": len(k8s_plan)},
    )

    verify_report_path: Path | None = None
    verify_ok: bool | None = None
    verify_blocker_kind: str | None = None
    verify_rbac_hint: str | None = None
    apply_report_path: Path | None = None
    k8s_apply_rc: int | None = None
    apply_ok: bool | None = None
    apply_attempted = False
    apply_blocked_reason: str | None = None

    kill_switch_eval = _evaluate_kill_switch_signal()
    kill_switch_active = bool(kill_switch_eval.get("active"))
    kill_switch_signal = (
        str(kill_switch_eval.get("signal")) if kill_switch_eval.get("signal") else None
    )
    license_gate: dict[str, object] | None = None
    paid_enabled = False

    if apply_requested and not proposed:
        explain.emit("closed_loop_apply_skipped", {"reason": "no_proposals"})
    elif apply_requested and not executable_actions:
        explain.emit("closed_loop_apply_skipped", {"reason": "no_approved_proposals"})
    elif apply_requested:
        rc, verify_path, verify_report = _run_k8s_verify(k8s_plan_path, out_dir, explain)
        verify_report_path = verify_path
        if verify_report and isinstance(verify_report, dict):
            verify_ok = bool(verify_report.get("ok") is True)
            verify_blocker = verify_report.get("verify_blocker")
            if isinstance(verify_blocker, dict):
                kind = verify_blocker.get("kind")
                if isinstance(kind, str) and kind.strip():
                    verify_blocker_kind = kind
            details = verify_report.get("details")
            if isinstance(details, dict):
                rbac = details.get("rbac")
                if isinstance(rbac, dict):
                    hint = rbac.get("hint")
                    if isinstance(hint, str) and hint.strip():
                        verify_rbac_hint = hint
        else:
            verify_ok = bool(rc == 0)
        license_gate = _resolve_apply_license_gate(
            kubectl=os.environ.get("KUBECTL", "kubectl"),
            license_path=license_path,
        )
        paid_enabled = bool(license_gate.get("internal_override") or license_gate.get("license_ok"))
        if kill_switch_active:
            apply_blocked_reason = _KILL_SWITCH_BLOCK_REASON
        else:
            apply_blocked_reason = (
                str(license_gate.get("block_reason")) if license_gate.get("block_reason") else None
            )

        if apply_blocked_reason:
            explain.emit(
                "closed_loop_apply_blocked",
                {
                    "reason": apply_blocked_reason,
                    "verify_ok": verify_ok,
                    "k8s_verify_report_path": str(verify_report_path) if verify_report_path else None,
                    "license_path": license_gate.get("license_path"),
                    "license_ok": license_gate.get("license_ok"),
                    "license_reason": license_gate.get("reason"),
                    "license_expires_at": license_gate.get("expires_at"),
                    "entitlements_summary": license_gate.get("entitlements_summary"),
                    "internal_override": license_gate.get("internal_override"),
                    "kill_switch_signal": kill_switch_signal,
                },
            )
            # Emit canonical k8s apply artifacts even for gated/blocked apply.
            k8s_apply_rc, blocked_apply_path, _ = _run_k8s_apply(
                k8s_plan_path,
                out_dir,
                explain,
                force=False,
                license_path=license_path,
            )
            apply_report_path = blocked_apply_path
        else:
            apply_attempted = True
            rc, apply_path, apply_report = _run_k8s_apply(
                k8s_plan_path,
                out_dir,
                explain,
                force=False,
                license_path=license_path,
            )
            k8s_apply_rc = rc
            apply_report_path = apply_path
            if apply_report and isinstance(apply_report, dict):
                apply_report_block_reason = str(apply_report.get("block_reason") or "")
                if rc == 2 and apply_report_block_reason:
                    apply_attempted = False
                    apply_ok = None
                    apply_blocked_reason = apply_report_block_reason
                    explain.emit(
                        "closed_loop_apply_blocked",
                        {
                            "reason": apply_blocked_reason,
                            "verify_ok": verify_ok,
                            "k8s_verify_report_path": (
                                str(verify_report_path) if verify_report_path else None
                            ),
                            "license_path": license_gate.get("license_path"),
                            "license_ok": license_gate.get("license_ok"),
                            "license_reason": license_gate.get("reason"),
                            "license_expires_at": license_gate.get("expires_at"),
                            "entitlements_summary": license_gate.get("entitlements_summary"),
                            "internal_override": license_gate.get("internal_override"),
                            "kill_switch_signal": kill_switch_signal,
                        },
                    )
                else:
                    apply_ok = bool(apply_report.get("ok") is True)
            else:
                apply_ok = rc == 0

    effective_dry_run = not apply_attempted
    cli_dry_run = not apply_requested

    explain.emit(
        "closed_loop_apply_result",
        {
            "dry_run": cli_dry_run,
            "apply_requested": apply_requested,
            "apply_attempted": apply_attempted,
            "apply_ok": apply_ok,
            "verify_ok": verify_ok,
            "blocked_reason": apply_blocked_reason,
            "apply_blocked_reason": apply_blocked_reason,
            "kill_switch_active": kill_switch_active,
            "kill_switch_signal": kill_switch_signal,
            "k8s_verify_report_path": str(verify_report_path) if verify_report_path else None,
            "k8s_apply_report_path": str(apply_report_path) if apply_report_path else None,
            "k8s_apply_rc": k8s_apply_rc,
        },
    )

    decision_summary = summarize_decision(signals, proposed)
    explain.emit(
        "policy_decision",
        {"decision_summary": decision_summary, "proposed": [p.to_dict() for p in proposed]},
    )

    if not apply_requested:
        apply_decision_summary = "apply not requested (dry-run)"
    elif apply_blocked_reason:
        apply_decision_summary = f"apply blocked: {apply_blocked_reason}"
    elif apply_attempted and apply_ok is True:
        apply_decision_summary = "apply executed: ok"
    elif apply_attempted:
        apply_decision_summary = "apply executed: failed"
    else:
        apply_decision_summary = "apply not attempted"

    results: list[dict] = []
    if proposed:
        for index, action in enumerate(proposed):
            approval_result = approval_blocked.get(index)
            if approval_result is not None:
                results.append(approval_result.to_dict())
                continue
            result = {
                "action": action.to_dict(),
                "applied": False,
                "blocked": False,
                "reason": "",
                "dry_run": bool(effective_dry_run),
            }
            if apply_blocked_reason:
                result.update(
                    {
                        "blocked": True,
                        "reason": apply_blocked_reason,
                        "dry_run": True,
                    }
                )
            elif not apply_requested:
                result.update(
                    {
                        "reason": "dry_run",
                        "dry_run": True,
                    }
                )
            elif apply_attempted:
                if apply_ok is True:
                    result.update(
                        {
                            "applied": True,
                            "reason": "k8s_apply",
                            "dry_run": False,
                        }
                    )
                elif apply_ok is False:
                    result.update(
                        {
                            "reason": "k8s_apply_failed",
                            "dry_run": False,
                        }
                    )
                else:
                    result.update(
                        {
                            "reason": "k8s_apply_unknown",
                            "dry_run": False,
                        }
                    )
            else:
                result.update(
                    {
                        "reason": "dry_run",
                        "dry_run": True,
                    }
                )
            results.append(result)

    trace_path = out_dir / "decision_trace_latest.jsonl"
    trace_actions = []
    for action in proposed:
        item = {
            "knob": action.knob,
            "target": action.target,
            "reason": action.reason,
        }
        if action.chord:
            item["chord"] = action.chord
        trace_actions.append(item)
    blocked_reasons = _count_blocked_reasons(results)
    chord_ids = sorted(
        {
            action.chord
            for action in proposed
            if isinstance(action.chord, str) and action.chord.strip()
        }
    )
    if len(chord_ids) == 1:
        chord: dict | str = {"id": chord_ids[0]}
    elif len(chord_ids) > 1:
        chord = {"id": "multi", "members": chord_ids}
    else:
        chord = {"id": "none"}
    trace_event = {
        "schema_version": DECISION_TRACE_SCHEMA_VERSION,
        "tick": int(tick),
        "mode": sm.mode.value,
        "signals": {
            "drift": bool(signals.get("drift")),
            "burst": bool(signals.get("burst")),
            "straggler": bool(signals.get("straggler")),
            "gpu_saturated": bool(signals.get("gpu_saturated")),
            "incident": bool(signals.get("incident")),
            "notes": [
                note
                for note in (signals.get("notes") or [])
                if isinstance(note, str)
            ],
        },
        "chord": chord,
        "actions": trace_actions,
        "results": {
            "apply_requested": bool(apply_requested),
            "dry_run": bool(cli_dry_run),
            "apply_attempted": bool(apply_attempted),
            "apply_ok": apply_ok,
            "verify_ok": verify_ok,
            "blocked_reason": apply_blocked_reason,
            "kill_switch_active": kill_switch_active,
            "kill_switch_signal": kill_switch_signal,
            "blocked_reasons": blocked_reasons,
        },
    }
    DecisionTraceWriter(trace_path).emit(trace_event)

    report_base = {
        "mode": sm.mode.value,
        "policy": policy,
        "signals": signals,
        "telemetry": _build_telemetry_payload(samples),
        "environment": _build_environment_fingerprint(samples),
        "proposed": [p.to_dict() for p in proposed],
        "proposed_actions_count": len(proposed),
        "opportunity_hours_est": opportunity.get("opportunity_hours_est"),
        "opportunity_tokens_est": opportunity.get("opportunity_tokens_est"),
        "opportunity_usd_est": opportunity.get("opportunity_usd_est"),
        "opportunity_assumptions": opportunity.get("opportunity_assumptions"),
        "value_summary": value_summary,
        "results": results,
        "applied": [r["action"] for r in results if r.get("applied")],
        "k8s_plan_path": str(k8s_plan_path),
        "k8s_plan_items": len(k8s_plan),
        "k8s_kubectl_plan_path": str(k8s_kubectl_plan_path),
        "k8s_namespace": k8s_namespace,
        "k8s_deployment": k8s_deployment,
        "dry_run": cli_dry_run,
        "apply_requested": apply_requested,
        "apply_attempted": apply_attempted,
        "apply_ok": apply_ok,
        "decision_summary": decision_summary,
        "kill_switch_active": kill_switch_active,
        "kill_switch_signal": kill_switch_signal,
        "paid_enabled": paid_enabled,
        "license_path": (license_gate or {}).get("license_path"),
        "license_ok": (license_gate or {}).get("license_ok"),
        "license_reason": (license_gate or {}).get("reason"),
        "license_expires_at": (license_gate or {}).get("expires_at"),
        "entitlements_summary": (license_gate or {}).get("entitlements_summary"),
        "internal_override": (license_gate or {}).get("internal_override"),
        "verify_ok": verify_ok,
        "verify_blocker_kind": verify_blocker_kind,
        "verify_rbac_hint": verify_rbac_hint,
        "k8s_verify_report_path": str(verify_report_path) if verify_report_path else None,
        "k8s_apply_report_path": str(apply_report_path) if apply_report_path else None,
        "k8s_apply_rc": k8s_apply_rc,
        "apply_blocked_reason": apply_blocked_reason,
        "apply_decision_summary": apply_decision_summary,
        "status": "ok",
        "blocked_reasons": blocked_reasons,
        "applied_reasons": _count_applied_reasons(results),
        "observe_record_raw_path": record_raw_path_value,
        "observe_record_raw_lines_written": (
            int(record_raw_lines_written) if observe_record_raw_path else None
        ),
        "safety_cooldown_s": int(guardrails.min_interval.total_seconds()),
        "safety_max_delta_per_step": int(guardrails.max_delta_per_step),
        "audit_trace": {
            "path": trace_path.name,
            "schema_version": DECISION_TRACE_SCHEMA_VERSION,
        },
    }
    if observe_source == "file":
        report_base["observe_ingest"] = source.observe_ingest
    finished_at = _utc_now()
    report = _build_report(
        report_base,
        started_at=started_at,
        finished_at=finished_at,
        out_dir=out_dir,
        mode=sm.mode.value,
        apply_requested=apply_requested,
        dry_run=cli_dry_run,
    )
    _write_closed_loop_summary(out_dir, report, proposed, results)
    report_path = _write_report(
        out_dir,
        report,
        prefix="closed_loop",
        latest_name="closed_loop_latest.json",
    )
    _emit_policy_bundle_latest(
        out_dir,
        policy_id=policy,
        policy_version="v1",
        policy_params={},
    )
    explain.emit("closed_loop_report", {"path": str(report_path)})
    return report, report_path


def cmd_closed_loop(args: argparse.Namespace) -> int:
    if bool(args.apply):
        kill_switch = _evaluate_kill_switch_signal()
        if bool(kill_switch.get("active")):
            return _run_closed_loop_pro_required(
                args,
                block_reason=_KILL_SWITCH_BLOCK_REASON,
                kill_switch_active=True,
                kill_switch_signal=(
                    str(kill_switch.get("signal")) if kill_switch.get("signal") else None
                ),
            )
        pro_cli_ext = _load_pro_cli_ext()
        if pro_cli_ext is not None and hasattr(pro_cli_ext, "cmd_closed_loop_apply"):
            return int(pro_cli_ext.cmd_closed_loop_apply(args))
        return _run_closed_loop_pro_required(args)

    observe_duration_ms = _parse_duration_ms(args.observe_duration)
    report, _ = _run_closed_loop_once(
        scenario=args.scenario,
        k8s_namespace=args.k8s_namespace,
        k8s_deployment=args.k8s_deployment,
        out_dir=Path(args.out),
        apply_requested=False,
        observe_source=args.observe_source,
        observe_path=Path(args.observe_path) if args.observe_path else None,
        observe_record_raw_path=Path(args.observe_record_raw)
        if args.observe_record_raw
        else None,
        observe_record_raw_mode="w",
        observe_duration_ms=observe_duration_ms,
        observe_container=args.observe_container,
        license_path=_resolve_license_path(getattr(args, "license_path", None)),
        policy=args.policy,
        cooldown_s=int(args.cooldown_s),
        approve_advanced=bool(args.approve_advanced),
        max_delta_per_step=int(args.max_delta_per_step),
        tick=0,
    )
    return 0


def _format_tristate(value: bool | None) -> str:
    if value is True:
        return "true"
    if value is False:
        return "false"
    return "n/a"


def _write_watch_latest(out_dir: Path, report: dict) -> Path:
    watch_path = out_dir / "watch_latest.json"
    watch_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return watch_path


def _write_watch_summary(out_dir: Path, report: dict) -> None:
    lines = [
        f"started_at: {report.get('started_at')}",
        f"finished_at: {report.get('finished_at')}",
        f"duration_s: {report.get('duration_s')}",
        f"interval_s: {report.get('interval_s')}",
        f"max_iterations: {report.get('max_iterations')}",
        f"iterations_done: {report.get('iterations_done')}",
        f"proposed_total: {report.get('proposed_total')}",
        f"applied_total: {report.get('applied_total')}",
        f"blocked_total: {report.get('blocked_total')}",
        f"verify_failed_total: {report.get('verify_failed_total')}",
        f"dry_run_total: {report.get('dry_run_total')}",
        f"apply_attempted_total: {report.get('apply_attempted_total')}",
        f"apply_ok_total: {report.get('apply_ok_total')}",
        f"apply_failed_total: {report.get('apply_failed_total')}",
        f"last_iteration_out_dir: {report.get('last_iteration_out_dir')}",
    ]
    observe_ingest = report.get("observe_ingest")
    if isinstance(observe_ingest, dict) and observe_ingest:
        parts = []
        for key in sorted(observe_ingest):
            value = observe_ingest.get(key)
            if isinstance(value, int):
                parts.append(f"{key}={value}")
        if parts:
            lines.append(f"observe_ingest: {' '.join(parts)}")
    # Debug pointers: make watch_summary.md self-sufficient and consistent with watch_latest.json.
    pointer_keys = [
        "watch_latest_path",
        "watch_summary_path",
        "last_iteration_report_path",
        "last_iteration_explain_path",
    ]

    def _render_pointer(value: str | None) -> str:
        if value is None:
            return "null"
        return value

    artifact_paths = report.get("artifact_paths")
    if isinstance(artifact_paths, dict):
        for key in pointer_keys:
            lines.append(f"{key}: {_render_pointer(artifact_paths.get(key))}")
    else:
        watch_latest_path = str(out_dir / "watch_latest.json")
        watch_summary_path = str(out_dir / "watch_summary.md")
        last_iter = report.get("last_iteration_out_dir")
        last_iteration_report_path: str | None = None
        last_iteration_explain_path: str | None = None
        if isinstance(last_iter, str) and last_iter:
            last_iter_dir = Path(last_iter)
            candidate = last_iter_dir / "closed_loop_latest.json"
            if candidate.exists():
                last_iteration_report_path = str(candidate)
            candidate = last_iter_dir / "explain.jsonl"
            if candidate.exists():
                last_iteration_explain_path = str(candidate)
        pointer_values = {
            "watch_latest_path": watch_latest_path,
            "watch_summary_path": watch_summary_path,
            "last_iteration_report_path": last_iteration_report_path,
            "last_iteration_explain_path": last_iteration_explain_path,
        }
        for key in pointer_keys:
            lines.append(f"{key}: {_render_pointer(pointer_values.get(key))}")
    (out_dir / "watch_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _build_watch_report(
    *,
    base_out_dir: Path,
    started_at: datetime,
    finished_at: datetime,
    interval_s: int | float,
    max_iterations: int | None,
    iterations_done: int,
    last_iteration_out_dir: str | None,
    totals: dict[str, int],
    observe_ingest_totals: dict[str, int] | None,
    observe_record_raw_path: Path | None,
    observe_record_raw_lines_total: int | None,
) -> dict:
    last_iter_dir = Path(last_iteration_out_dir) if last_iteration_out_dir else None
    last_iteration_report_path: str | None = None
    if last_iter_dir is not None:
        candidate = last_iter_dir / "closed_loop_latest.json"
        if candidate.exists():
            last_iteration_report_path = str(candidate)
    last_iteration_explain_path: str | None = None
    if last_iter_dir is not None:
        candidate = last_iter_dir / "explain.jsonl"
        if candidate.exists():
            last_iteration_explain_path = str(candidate)

    return {
        "schema_version": "v0",
        "started_at": _format_utc(started_at),
        "finished_at": _format_utc(finished_at),
        "duration_s": int((finished_at - started_at).total_seconds()),
        "interval_s": interval_s,
        "max_iterations": max_iterations,
        "iterations_done": iterations_done,
        "last_iteration_out_dir": last_iteration_out_dir,
        **totals,
        "observe_ingest": observe_ingest_totals,
        "observe_record_raw_path": str(observe_record_raw_path)
        if observe_record_raw_path
        else None,
        "observe_record_raw_lines_written": observe_record_raw_lines_total,
        "artifact_paths": {
            "watch_latest_path": str(base_out_dir / "watch_latest.json"),
            "watch_summary_path": str(base_out_dir / "watch_summary.md"),
            "last_iteration_report_path": last_iteration_report_path,
            "last_iteration_explain_path": last_iteration_explain_path,
        },
    }


def _cmd_closed_loop_watch_legacy(args: argparse.Namespace) -> int:

    base_out_dir = _ensure_out_dir(args.out)
    interval_ms = int(args.interval)
    interval_s = _duration_ms_to_seconds(interval_ms)
    observe_duration_ms = _parse_duration_ms(args.observe_duration)
    max_iterations = args.max_iterations
    fallback_iterations = int(getattr(args, "iterations", 0) or 0)
    effective_max_iterations = max_iterations if max_iterations is not None else (
        fallback_iterations if fallback_iterations > 0 else None
    )
    observe_record_raw_path = (
        Path(args.observe_record_raw) if args.observe_record_raw else None
    )
    observe_record_raw_lines_total: int | None = (
        0 if observe_record_raw_path else None
    )
    resolved_license_path = _resolve_license_path(getattr(args, "license_path", None))
    license_error_emitted = False
    verify_error_emitted = False
    verify_gate_blocked = False
    started_at = _utc_now()
    iterations_done = 0
    stop_requested = False

    def _signal_handler(signum: int, _frame: object | None) -> None:
        nonlocal stop_requested
        stop_requested = True

    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    totals = {
        "proposed_total": 0,
        "applied_total": 0,
        "blocked_total": 0,
        "verify_failed_total": 0,
        "apply_attempted_total": 0,
        "apply_ok_total": 0,
        "apply_failed_total": 0,
        "dry_run_total": 0,
    }
    observe_ingest_totals: dict[str, int] | None = None
    last_iteration_out_dir: str | None = None

    try:
        while True:
            if stop_requested:
                break
            if effective_max_iterations is not None and iterations_done >= effective_max_iterations:
                break

            iteration = iterations_done + 1
            iter_dir = base_out_dir / f"iter_{iteration:04d}"
            report, _ = _run_closed_loop_once(
                scenario=args.scenario,
                k8s_namespace=args.k8s_namespace,
                k8s_deployment=args.k8s_deployment,
                out_dir=iter_dir,
                apply_requested=bool(args.apply),
                observe_source=args.observe_source,
                observe_path=Path(args.observe_path) if args.observe_path else None,
                observe_record_raw_path=observe_record_raw_path,
                observe_record_raw_mode="a",
                observe_duration_ms=observe_duration_ms,
                observe_container=args.observe_container,
                license_path=resolved_license_path,
                policy=args.policy,
                cooldown_s=int(args.cooldown_s),
                approve_advanced=bool(args.approve_advanced),
                max_delta_per_step=int(args.max_delta_per_step),
                tick=iteration - 1,
            )

            iterations_done += 1
            last_iteration_out_dir = str(iter_dir)

            totals["proposed_total"] += len(report.get("proposed", []))
            totals["applied_total"] += sum((report.get("applied_reasons") or {}).values())
            totals["blocked_total"] += sum((report.get("blocked_reasons") or {}).values())
            if report.get("verify_ok") is False:
                totals["verify_failed_total"] += 1
            if report.get("apply_attempted") is True:
                totals["apply_attempted_total"] += 1
                if report.get("apply_ok") is True:
                    totals["apply_ok_total"] += 1
                elif report.get("apply_ok") is False:
                    totals["apply_failed_total"] += 1
            if report.get("apply_requested") is False:
                totals["dry_run_total"] += 1

            observe_ingest = report.get("observe_ingest")
            if isinstance(observe_ingest, dict):
                for key, value in observe_ingest.items():
                    if isinstance(value, int):
                        if observe_ingest_totals is None:
                            observe_ingest_totals = {}
                        observe_ingest_totals[key] = observe_ingest_totals.get(key, 0) + value
            if observe_record_raw_lines_total is not None:
                lines_written = report.get("observe_record_raw_lines_written")
                if isinstance(lines_written, int):
                    observe_record_raw_lines_total += lines_written

            watch_report = _build_watch_report(
                base_out_dir=base_out_dir,
                started_at=started_at,
                finished_at=_utc_now(),
                interval_s=interval_s,
                max_iterations=max_iterations,
                iterations_done=iterations_done,
                last_iteration_out_dir=last_iteration_out_dir,
                totals=totals,
                observe_ingest_totals=observe_ingest_totals,
                observe_record_raw_path=observe_record_raw_path,
                observe_record_raw_lines_total=observe_record_raw_lines_total,
            )
            _write_watch_latest(base_out_dir, watch_report)
            _write_watch_summary(base_out_dir, watch_report)

            verify_ok = _format_tristate(report.get("verify_ok"))
            apply_ok = _format_tristate(report.get("apply_ok"))
            blocked_reason = report.get("apply_blocked_reason") or "null"
            print(
                " ".join(
                    [
                        f"iter={iteration}",
                        f"verify_ok={verify_ok}",
                        f"apply_attempted={bool(report.get('apply_attempted'))}",
                        f"apply_ok={apply_ok}",
                        f"blocked={blocked_reason}",
                        f"out={iter_dir}",
                    ]
                )
            )
            if bool(args.apply) and not license_error_emitted:
                blocked_reason = str(report.get("apply_blocked_reason") or "")
                if blocked_reason in {"license_missing", "license_invalid"}:
                    _emit_apply_block_error(blocked_reason)
                    license_error_emitted = True
            if bool(args.apply):
                blocked_reason = str(report.get("apply_blocked_reason") or "")
                if _is_verify_gate_reason(blocked_reason):
                    verify_gate_blocked = True
                    if not verify_error_emitted:
                        _emit_apply_block_error(blocked_reason)
                        verify_error_emitted = True

            if effective_max_iterations is not None and iterations_done >= effective_max_iterations:
                break
            if stop_requested:
                break
            if interval_s > 0:
                try:
                    time.sleep(float(interval_s))
                except InterruptedError:
                    pass
                except OSError as exc:
                    if exc.errno != errno.EINTR:
                        raise
            if stop_requested:
                break
    finally:
        final_report = _build_watch_report(
            base_out_dir=base_out_dir,
            started_at=started_at,
            finished_at=_utc_now(),
            interval_s=interval_s,
            max_iterations=max_iterations,
            iterations_done=iterations_done,
            last_iteration_out_dir=last_iteration_out_dir,
            totals=totals,
            observe_ingest_totals=observe_ingest_totals,
            observe_record_raw_path=observe_record_raw_path,
            observe_record_raw_lines_total=observe_record_raw_lines_total,
        )
        _write_watch_latest(base_out_dir, final_report)
        _write_watch_summary(base_out_dir, final_report)

    if verify_gate_blocked:
        return 2
    return 0


def cmd_closed_loop_watch(args: argparse.Namespace) -> int:
    if bool(args.apply):
        kill_switch = _evaluate_kill_switch_signal()
        if bool(kill_switch.get("active")):
            base_out_dir = _ensure_out_dir(args.out)
            interval_ms = int(args.interval)
            interval_s = _duration_ms_to_seconds(interval_ms)
            _write_watch_pro_required_artifacts(
                base_out_dir,
                interval_s,
                args.max_iterations,
                block_reason=_KILL_SWITCH_BLOCK_REASON,
            )
            _emit_kill_switch_error()
            return 2
        pro_cli_ext = _load_pro_cli_ext()
        if pro_cli_ext is not None and hasattr(pro_cli_ext, "cmd_closed_loop_watch_apply"):
            return int(pro_cli_ext.cmd_closed_loop_watch_apply(args))
        base_out_dir = _ensure_out_dir(args.out)
        interval_ms = int(args.interval)
        interval_s = _duration_ms_to_seconds(interval_ms)
        _write_watch_pro_required_artifacts(base_out_dir, interval_s, args.max_iterations)
        return _require_pro("closed-loop watch --apply")
    return _cmd_closed_loop_watch_legacy(args)


def cmd_demo(args: argparse.Namespace) -> int:
    started_at = _utc_now()
    out_dir = _ensure_out_dir(args.out)
    explain = ExplainLog(out_dir / "explain.jsonl")
    explain.emit("demo_start", {"scenario": args.scenario, "out": str(out_dir)})
    report_base = run_demo(args.scenario, out_dir, explain)
    finished_at = _utc_now()
    report = _build_report(
        report_base,
        started_at=started_at,
        finished_at=finished_at,
        out_dir=out_dir,
        mode="DEMO",
        apply_requested=False,
        dry_run=True,
    )
    report_path = _write_report(
        out_dir,
        report,
        prefix="demo",
        latest_name="demo_latest.json",
    )
    explain.emit("demo_report", {"path": str(report_path)})
    rc = 0
    explain.emit("demo_stop", {"scenario": args.scenario, "rc": rc})
    return rc


def _parse_contexts_csv(value: str | None) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def cmd_fleet_inventory(args: argparse.Namespace) -> int:
    out_dir = _ensure_out_dir(args.out)
    contexts: list[str] | None = None
    if args.contexts:
        contexts = _parse_contexts_csv(args.contexts)
    elif args.context:
        contexts = [item.strip() for item in args.context if item and item.strip()]

    report = collect_inventory(contexts=contexts, kubectl=os.environ.get("KUBECTL", "kubectl"))
    (out_dir / "inventory_latest.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return 0


def cmd_fleet_policy(args: argparse.Namespace) -> int:
    out_dir = _ensure_out_dir(args.out)
    contexts: list[str] | None = None
    if args.contexts:
        contexts = _parse_contexts_csv(args.contexts)
    elif args.context:
        contexts = [item.strip() for item in args.context if item and item.strip()]

    report = collect_policy_propagation(
        contexts=contexts,
        policy_ref=args.policy,
        kubectl=os.environ.get("KUBECTL", "kubectl"),
    )
    (out_dir / "policy_propagation_latest.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return 0


def cmd_demo_mk068(args: argparse.Namespace) -> int:
    try:
        out_dir = _ensure_out_dir(args.out)
        run_mk068_demo(out_dir=out_dir)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    return 0


def cmd_roi_mk074(args: argparse.Namespace) -> int:
    out_dir = _ensure_out_dir(args.out)
    try:
        observe_path = Path(args.observe_path) if args.observe_path else None
        samples, _ = _collect_observe_samples(
            scenario="baseline",
            observe_source=args.observe_source,
            observe_path=observe_path,
            k8s_namespace=getattr(args, "k8s_namespace", "default"),
            k8s_deployment=getattr(args, "k8s_deployment", "trainer"),
            observe_container=getattr(args, "observe_container", "auto"),
            observe_duration_ms=_parse_duration_ms(getattr(args, "observe_duration", "60s")),
            observe_record_raw_path=None,
            observe_record_raw_mode="w",
            required_path_flag="--observe-path",
            required_source_flag="--observe-source",
        )
        before, after, combined = build_mk074_before_after(
            samples=samples,
            observe_source=args.observe_source,
            observe_path=(observe_path.name if observe_path else None),
        )
        (out_dir / "mk074_before_latest.json").write_text(
            json.dumps(before, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        (out_dir / "mk074_after_latest.json").write_text(
            json.dumps(after, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        (out_dir / "mk074_before_after_latest.json").write_text(
            json.dumps(combined, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    except (Exception, SystemExit) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    return 0


def cmd_roi_estimate(args: argparse.Namespace) -> int:
    out_dir = _ensure_out_dir(args.out)
    try:
        observe_path = Path(args.observe_path)
        source = FileSource(path=observe_path)
        samples = source.read()
        report = estimate_roi(samples)
        (out_dir / "roi_estimate_latest.json").write_text(
            json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    except (Exception, SystemExit) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    return 0


def _read_json_best_effort(path: Path) -> tuple[dict | None, str | None]:
    if not path.exists():
        return None, "missing_file"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None, "invalid_json"
    if not isinstance(payload, dict):
        return None, "invalid_json_shape"
    return payload, None


def _report_bool(value: bool) -> str:
    return "true" if value else "false"


def _render_roi_summary_md(
    *,
    started_at: str,
    finished_at: str,
    duration_s: int,
    ok: bool,
    top_blocker: str | None,
    environment: dict | None,
    preflight_visibility: dict | None,
    watch_summary: dict | None,
    opportunity_hours_est: float | int | None,
    proposed_actions_count: int,
    notes: list[str],
) -> str:
    env = environment if isinstance(environment, dict) else {}
    preflight = preflight_visibility if isinstance(preflight_visibility, dict) else {}
    watch = watch_summary if isinstance(watch_summary, dict) else {}

    lines = [
        "# ROI value report",
        f"started_at: {started_at}",
        f"finished_at: {finished_at}",
        f"duration_s: {duration_s}",
        f"ok: {_report_bool(ok)}",
        f"top_blocker: {top_blocker or 'n/a'}",
        f"environment.unstable: {env.get('unstable') if env else 'n/a'}",
        f"environment.nodes_seen: {json.dumps(env.get('nodes_seen') or [], separators=(',', ':'), ensure_ascii=False)}",
        f"environment.gpu_models_seen: {json.dumps(env.get('gpu_models_seen') or [], separators=(',', ':'), ensure_ascii=False)}",
        f"preflight.gpu_capacity_present: {preflight.get('gpu_capacity_present') if preflight else 'n/a'}",
        f"preflight.device_plugin_present: {preflight.get('device_plugin_present') if preflight else 'n/a'}",
        f"preflight.deploy_gpu_request: {preflight.get('deploy_gpu_request') if preflight else 'n/a'}",
        f"preflight.notes: {json.dumps(preflight.get('notes') or [], separators=(',', ':'), ensure_ascii=False)}",
        f"watch.duration_s: {watch.get('duration_s') if watch else 'n/a'}",
        f"watch.iterations_done: {watch.get('iterations_done') if watch else 'n/a'}",
        f"watch.interval_s: {watch.get('interval_s') if watch else 'n/a'}",
        f"watch.proposed_total: {watch.get('proposed_total') if watch else 'n/a'}",
        f"watch.applied_total: {watch.get('applied_total') if watch else 'n/a'}",
        f"watch.blocked_total: {watch.get('blocked_total') if watch else 'n/a'}",
        f"opportunity_hours_est: {opportunity_hours_est if opportunity_hours_est is not None else 'n/a'}",
        f"proposed_actions_count: {proposed_actions_count}",
        "",
        "## Что делать дальше",
    ]

    next_steps: list[str] = []
    note_set = set(item for item in notes if isinstance(item, str))
    blocker_set = set(note_set)
    if isinstance(top_blocker, str) and top_blocker:
        blocker_set.add(top_blocker)
    if "loss_missing" in blocker_set:
        next_steps.append("подключить метрику loss/throughput")
        next_steps.append("запустить на реальной нагрузке")
    if "gpu_not_in_cluster" in blocker_set:
        next_steps.append("GPU-enable cluster")
    if "device_plugin_missing" in blocker_set:
        next_steps.append("поставить device plugin")
    if "deploy_not_requesting_gpu" in blocker_set:
        next_steps.append("добавить requests")
    if not next_steps:
        next_steps.append("проверить корректность входных отчётов preflight/eval/watch")
    dedup_steps = list(dict.fromkeys(next_steps))[:3]
    for step in dedup_steps:
        lines.append(f"- {step}")
    return "\n".join(lines) + "\n"


def cmd_roi_report(args: argparse.Namespace) -> int:
    started_at = _utc_now()
    out_dir = _ensure_out_dir(args.out)
    explain = ExplainLog(out_dir / "explain.jsonl")

    preflight_path = Path(args.preflight)
    eval_path = Path(args.eval)
    watch_path = Path(args.watch)
    explain.emit(
        "roi_start",
        {
            "out": str(out_dir),
            "preflight_path": str(preflight_path),
            "eval_path": str(eval_path),
            "watch_path": str(watch_path),
        },
    )

    parse_errors: list[dict] = []
    preflight, preflight_error = _read_json_best_effort(preflight_path)
    if preflight_error:
        parse_errors.append({"input": "preflight", "path": str(preflight_path), "reason": preflight_error})
    eval_report, eval_error = _read_json_best_effort(eval_path)
    if eval_error:
        parse_errors.append({"input": "eval", "path": str(eval_path), "reason": eval_error})
    watch, watch_error = _read_json_best_effort(watch_path)
    if watch_error:
        parse_errors.append({"input": "watch", "path": str(watch_path), "reason": watch_error})

    explain.emit(
        "roi_read_inputs",
        {
            "inputs": {
                "preflight": {"path": str(preflight_path), "ok": preflight_error is None},
                "eval": {"path": str(eval_path), "ok": eval_error is None},
                "watch": {"path": str(watch_path), "ok": watch_error is None},
            }
        },
    )
    if parse_errors:
        explain.emit("roi_parse_errors", {"errors": parse_errors})

    ingest_ok = len(parse_errors) == 0
    notes: set[str] = set()
    blockers: list[str] = []
    if parse_errors:
        first = parse_errors[0]
        blockers.append(f"{first['input']}_{first['reason']}")

    def _pick_blocker(report: dict | None) -> str | None:
        if not isinstance(report, dict):
            return None
        value = report.get("top_blocker")
        if isinstance(value, str) and value.strip():
            return value.strip()
        return None

    preflight_blocker = _pick_blocker(preflight)
    if preflight_blocker:
        blockers.append(preflight_blocker)
    eval_blocker = _pick_blocker(eval_report)
    if eval_blocker:
        blockers.append(eval_blocker)
    watch_blocker = _pick_blocker(watch)
    if watch_blocker:
        blockers.append(watch_blocker)

    environment: dict | None = None
    if isinstance(eval_report, dict) and isinstance(eval_report.get("environment"), dict):
        environment = eval_report.get("environment")

    preflight_visibility: dict | None = None
    if isinstance(preflight, dict):
        preflight_notes = preflight.get("notes")
        preflight_notes_list = sorted(item for item in preflight_notes if isinstance(item, str)) if isinstance(preflight_notes, list) else []
        for item in preflight_notes_list:
            notes.add(item)
        device_plugin_present = preflight.get("device_plugin_present")
        if device_plugin_present is None:
            device_plugin_present = preflight.get("nvidia_device_plugin_present")
        preflight_visibility = {
            "gpu_capacity_present": preflight.get("gpu_capacity_present"),
            "device_plugin_present": device_plugin_present,
            "deploy_gpu_request": preflight.get("deploy_gpu_request"),
            "notes": preflight_notes_list,
        }

    watch_summary: dict | None = None
    proposed_total = 0
    if isinstance(watch, dict):
        watch_summary = {
            "duration_s": watch.get("duration_s"),
            "iterations_done": watch.get("iterations_done"),
            "interval_s": watch.get("interval_s"),
            "proposed_total": watch.get("proposed_total"),
            "applied_total": watch.get("applied_total"),
            "blocked_total": watch.get("blocked_total"),
            "last_iteration_out_dir": watch.get("last_iteration_out_dir"),
        }
        proposed_value = watch.get("proposed_total")
        if isinstance(proposed_value, int):
            proposed_total = proposed_value

    last_iteration_report_path: Path | None = None
    if isinstance(watch, dict):
        direct = watch.get("last_iteration_report_path")
        if isinstance(direct, str) and direct.strip():
            last_iteration_report_path = Path(direct.strip())
        artifacts = watch.get("artifact_paths")
        if last_iteration_report_path is None and isinstance(artifacts, dict):
            candidate = artifacts.get("last_iteration_report_path")
            if isinstance(candidate, str) and candidate.strip():
                last_iteration_report_path = Path(candidate.strip())

    last_iteration_report: dict | None = None
    if last_iteration_report_path is not None:
        last_iteration_report, last_iteration_error = _read_json_best_effort(last_iteration_report_path)
        if last_iteration_error:
            notes.add(f"last_iteration_report_{last_iteration_error}")

    if environment is None and isinstance(last_iteration_report, dict):
        env_fallback = last_iteration_report.get("environment")
        if isinstance(env_fallback, dict):
            environment = env_fallback

    eval_notes = (((eval_report or {}).get("signals") or {}).get("notes")) if isinstance(eval_report, dict) else None
    watch_notes = (((last_iteration_report or {}).get("signals") or {}).get("notes")) if isinstance(last_iteration_report, dict) else None
    has_loss_missing = (
        (isinstance(eval_notes, list) and any(item == "loss_missing" for item in eval_notes))
        or (isinstance(watch_notes, list) and any(item == "loss_missing" for item in watch_notes))
    )
    if has_loss_missing:
        if proposed_total == 0 and not blockers:
            blockers.append("loss_missing")
        else:
            notes.add("loss_missing")

    opportunity_hours_est: float | int | None = None
    proposed_actions_count = 0
    if isinstance(last_iteration_report, dict):
        value = last_iteration_report.get("opportunity_hours_est")
        if isinstance(value, (int, float)):
            opportunity_hours_est = value
        proposed_actions_value = last_iteration_report.get("proposed_actions_count")
        if isinstance(proposed_actions_value, int):
            proposed_actions_count = proposed_actions_value

    top_blocker = blockers[0] if blockers else None
    ok = bool(ingest_ok and top_blocker is None)
    finished_at = _utc_now()
    roi_path = out_dir / "roi_latest.json"
    summary_path = out_dir / "roi_summary.md"
    notes_list = sorted(item for item in notes if isinstance(item, str))
    key_artifacts = sorted(
        {
            str(roi_path),
            str(summary_path),
            str(out_dir / "explain.jsonl"),
        }
    )
    report = {
        "schema_version": "roi.v0",
        "started_at": _format_utc(started_at),
        "finished_at": _format_utc(finished_at),
        "duration_s": int((finished_at - started_at).total_seconds()),
        "ingest_ok": ingest_ok,
        "ok": ok,
        "top_blocker": top_blocker,
        "inputs": {
            "preflight_path": str(preflight_path),
            "eval_path": str(eval_path),
            "watch_path": str(watch_path),
        },
        "environment": environment,
        "preflight_visibility": preflight_visibility,
        "watch_summary": watch_summary,
        "opportunity_hours_est": opportunity_hours_est,
        "proposed_actions_count": proposed_actions_count,
        "notes": notes_list,
        "key_artifacts": key_artifacts,
    }
    summary_md = _render_roi_summary_md(
        started_at=report["started_at"],
        finished_at=report["finished_at"],
        duration_s=report["duration_s"],
        ok=ok,
        top_blocker=top_blocker,
        environment=environment,
        preflight_visibility=preflight_visibility,
        watch_summary=watch_summary,
        opportunity_hours_est=opportunity_hours_est,
        proposed_actions_count=proposed_actions_count,
        notes=notes_list,
    )

    explain.emit(
        "roi_computed",
        {
            "ok": ok,
            "ingest_ok": ingest_ok,
            "top_blocker": top_blocker,
            "notes": notes_list,
            "opportunity_hours_est": opportunity_hours_est,
            "proposed_actions_count": proposed_actions_count,
        },
    )
    roi_path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    summary_path.write_text(summary_md, encoding="utf-8")
    explain.emit(
        "roi_written",
        {"roi_path": str(roi_path), "summary_path": str(summary_path), "ok": ok},
    )
    print(
        " ".join(
            [
                f"roi_ok={_report_bool(ok)}",
                f"top_blocker={top_blocker or 'n/a'}",
                f"opportunity_hours_est={opportunity_hours_est if opportunity_hours_est is not None else 'n/a'}",
                f"roi={roi_path}",
                f"summary={summary_path}",
            ]
        )
    )
    return 0


def _find_first_named(root: Path, name: str) -> Path | None:
    matches: list[Path] = []
    for candidate in root.rglob(name):
        if candidate.is_file():
            matches.append(candidate)
    if not matches:
        return None
    return sorted(matches, key=lambda item: item.relative_to(root).as_posix())[0]


def _normalize_candidate_path(base_dir: Path, value: object) -> Path | None:
    if not isinstance(value, str) or not value.strip():
        return None
    path = Path(value.strip())
    if not path.is_absolute():
        path = (base_dir / path).resolve()
    return path


def _extract_environment_fingerprint(eval_report: dict | None, watch_report: dict | None, notes: list[str]) -> dict | None:
    if isinstance(eval_report, dict):
        env = eval_report.get("environment")
        if isinstance(env, dict):
            return env

    if not isinstance(watch_report, dict):
        return None

    candidate = _normalize_candidate_path(
        base_dir=watch_report.get("__path", Path(".")),
        value=watch_report.get("last_iteration_report_path"),
    )
    if candidate is None:
        artifacts = watch_report.get("artifact_paths")
        if isinstance(artifacts, dict):
            candidate = _normalize_candidate_path(
                base_dir=watch_report.get("__path", Path(".")),
                value=artifacts.get("last_iteration_report_path"),
            )
    if candidate is None:
        return None
    payload, error = _read_json_best_effort(candidate)
    if error:
        notes.append(f"environment_fallback_{error}")
        return None
    env = payload.get("environment") if isinstance(payload, dict) else None
    if isinstance(env, dict):
        return env
    return None


def _bundle_kind(rel_path: str) -> str:
    name = Path(rel_path).name
    if name == "preflight_latest.json":
        return "preflight"
    if name == "eval_latest.json":
        return "eval"
    if name == "watch_latest.json":
        return "watch"
    if name == "roi_latest.json":
        return "roi"
    if name.endswith("_summary.md") or name == "summary.md":
        return "summary"
    if name == "explain.jsonl":
        return "explain"
    return "other"


def _build_bundle_file_entry(in_dir: Path, file_path: Path) -> dict:
    rel_path = file_path.relative_to(in_dir).as_posix()
    schema_version = None
    if file_path.suffix.lower() == ".json":
        payload, _ = _read_json_best_effort(file_path)
        if isinstance(payload, dict):
            value = payload.get("schema_version")
            if isinstance(value, str):
                schema_version = value
    return {
        "rel_path": rel_path,
        "sha256": sha256_file(file_path),
        "size_bytes": int(file_path.stat().st_size),
        "schema_version": schema_version,
        "kind": _bundle_kind(rel_path),
    }


def _build_bundle_tar(tar_path: Path, manifest_path: Path, manifest_rel_path: str, files: list[dict], in_dir: Path) -> None:
    with tar_path.open("wb") as raw_handle:
        with gzip.GzipFile(filename="", mode="wb", fileobj=raw_handle, mtime=0) as gz_handle:
            with tarfile.open(fileobj=gz_handle, mode="w", format=tarfile.PAX_FORMAT) as tar:
                manifest_bytes = manifest_path.read_bytes()
                info = tarfile.TarInfo(name=manifest_rel_path)
                info.size = len(manifest_bytes)
                info.mtime = 0
                info.uid = 0
                info.gid = 0
                info.uname = ""
                info.gname = ""
                tar.addfile(info, BytesIO(manifest_bytes))

                for item in files:
                    rel_path = str(item.get("rel_path", ""))
                    if not rel_path:
                        continue
                    source_path = in_dir / rel_path
                    if not source_path.exists() or not source_path.is_file():
                        continue
                    data = source_path.read_bytes()
                    file_info = tarfile.TarInfo(name=rel_path)
                    file_info.size = len(data)
                    file_info.mtime = 0
                    file_info.uid = 0
                    file_info.gid = 0
                    file_info.uname = ""
                    file_info.gname = ""
                    tar.addfile(file_info, BytesIO(data))


def cmd_export_bundle(args: argparse.Namespace) -> int:
    in_dir = Path(args.input_dir)
    out_dir = _ensure_out_dir(args.out)
    started_at = _utc_now()

    notes: list[str] = []
    selected_paths: dict[str, Path] = {}
    include_paths: dict[str, Path] = {}
    known_artifacts = [
        "preflight_latest.json",
        "eval_latest.json",
        "watch_latest.json",
        "roi_latest.json",
    ]
    for name in known_artifacts:
        found = _find_first_named(in_dir, name)
        if found is None:
            notes.append(f"missing_{name}")
            continue
        selected_paths[name] = found
        include_paths[found.resolve().as_posix()] = found
        summary_name = name.replace("_latest.json", "_summary.md")
        summary_path = found.parent / summary_name
        if summary_path.exists() and summary_path.is_file():
            include_paths[summary_path.resolve().as_posix()] = summary_path
        generic_summary_path = found.parent / "summary.md"
        if generic_summary_path.exists() and generic_summary_path.is_file():
            include_paths[generic_summary_path.resolve().as_posix()] = generic_summary_path
        explain_path = found.parent / "explain.jsonl"
        if explain_path.exists() and explain_path.is_file():
            include_paths[explain_path.resolve().as_posix()] = explain_path
        prefix = name.replace("_latest.json", "")
        ts_pattern = re.compile(rf"^{re.escape(prefix)}_\d{{8}}_\d{{6}}\.json$")
        for sibling in sorted(found.parent.iterdir()):
            if not sibling.is_file():
                continue
            if ts_pattern.match(sibling.name):
                include_paths[sibling.resolve().as_posix()] = sibling

    eval_report, _ = _read_json_best_effort(selected_paths["eval_latest.json"]) if "eval_latest.json" in selected_paths else (None, None)
    watch_report, _ = _read_json_best_effort(selected_paths["watch_latest.json"]) if "watch_latest.json" in selected_paths else (None, None)
    roi_report, _ = _read_json_best_effort(selected_paths["roi_latest.json"]) if "roi_latest.json" in selected_paths else (None, None)

    if isinstance(watch_report, dict) and "watch_latest.json" in selected_paths:
        watch_report["__path"] = selected_paths["watch_latest.json"].parent.resolve()
    environment = _extract_environment_fingerprint(eval_report, watch_report, notes)
    if isinstance(watch_report, dict) and "__path" in watch_report:
        watch_report.pop("__path", None)

    file_entries = [
        _build_bundle_file_entry(in_dir, path)
        for path in sorted(include_paths.values(), key=lambda item: item.relative_to(in_dir).as_posix())
    ]

    run_seed_parts = [f"{item['rel_path']}:{item['sha256']}" for item in file_entries]
    run_seed = "\n".join(run_seed_parts) if run_seed_parts else "no-files"
    run_id = hashlib.sha256(run_seed.encode("utf-8")).hexdigest()

    metering = {
        "sample_count": eval_report.get("sample_count") if isinstance(eval_report, dict) else None,
        "watch": {
            "duration_s": watch_report.get("duration_s") if isinstance(watch_report, dict) else None,
            "iterations_done": watch_report.get("iterations_done") if isinstance(watch_report, dict) else None,
            "proposed_total": watch_report.get("proposed_total") if isinstance(watch_report, dict) else None,
            "blocked_total": watch_report.get("blocked_total") if isinstance(watch_report, dict) else None,
            "applied_total": watch_report.get("applied_total") if isinstance(watch_report, dict) else None,
        },
        "roi": {
            "opportunity_hours_est": roi_report.get("opportunity_hours_est") if isinstance(roi_report, dict) else None,
            "proposed_actions_count": roi_report.get("proposed_actions_count") if isinstance(roi_report, dict) else None,
            "ok": roi_report.get("ok") if isinstance(roi_report, dict) else None,
            "top_blocker": roi_report.get("top_blocker") if isinstance(roi_report, dict) else None,
        },
    }

    manifest = {
        "schema_version": "bundle.v0",
        "created_at": _format_utc(started_at),
        "tool_version": MK_VERSION,
        "run_id": run_id,
        "inputs_root": str(in_dir),
        "metering": metering,
        "environment": environment,
        "files": file_entries,
        "notes": sorted(notes),
    }
    manifest_valid = (
        manifest.get("schema_version") == "bundle.v0"
        and isinstance(manifest.get("files"), list)
        and isinstance(manifest.get("run_id"), str)
        and bool(manifest.get("run_id"))
    )
    ok = bool(manifest_valid)

    manifest_path = out_dir / "bundle_manifest.json"
    tar_path = out_dir / "bundle.tar.gz"
    summary_path = out_dir / "bundle_summary.md"

    try:
        manifest_path.write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        _build_bundle_tar(
            tar_path=tar_path,
            manifest_path=manifest_path,
            manifest_rel_path="bundle_manifest.json",
            files=file_entries,
            in_dir=in_dir,
        )
        top_blocker = metering["roi"].get("top_blocker")
        summary_lines = [
            "# Bundle export",
            f"ok: {_report_bool(ok)}",
            f"inputs_root: {in_dir}",
            f"files_count: {len(file_entries)}",
            f"sample_count: {metering.get('sample_count')}",
            f"watch.duration_s: {metering['watch'].get('duration_s')}",
            f"watch.iterations_done: {metering['watch'].get('iterations_done')}",
            f"watch.proposed_total: {metering['watch'].get('proposed_total')}",
            f"watch.blocked_total: {metering['watch'].get('blocked_total')}",
            f"watch.applied_total: {metering['watch'].get('applied_total')}",
            f"roi.opportunity_hours_est: {metering['roi'].get('opportunity_hours_est')}",
            f"roi.proposed_actions_count: {metering['roi'].get('proposed_actions_count')}",
            f"roi.ok: {metering['roi'].get('ok')}",
            f"top_blocker: {top_blocker if isinstance(top_blocker, str) and top_blocker else 'n/a'}",
            f"notes: {json.dumps(sorted(notes), ensure_ascii=False, separators=(',', ':'))}",
            f"manifest: {manifest_path}",
            f"tar: {tar_path}",
        ]
        summary_path.write_text("\n".join(summary_lines) + "\n", encoding="utf-8")
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    top_blocker = metering["roi"].get("top_blocker")
    top_blocker_text = top_blocker if isinstance(top_blocker, str) and top_blocker.strip() else "n/a"
    print(
        " ".join(
            [
                f"bundle_ok={_report_bool(ok)}",
                f"top_blocker={top_blocker_text}",
                f"manifest={manifest_path}",
                f"tar={tar_path}",
                f"summary={summary_path}",
                f"files={len(file_entries)}",
            ]
        )
    )
    return 0


def cmd_passport_templates(_args: argparse.Namespace) -> int:
    for name in passports_list_templates():
        print(name)
    return 0


def cmd_passport_show(args: argparse.Namespace) -> int:
    try:
        passport = load_template(args.template)
    except PassportValidationError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    print(json.dumps(asdict(passport), indent=2, ensure_ascii=False))
    return 0


def cmd_passport_validate(args: argparse.Namespace) -> int:
    try:
        load_passport(Path(args.file))
    except PassportValidationError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    return 0


def cmd_chords_validate(args: argparse.Namespace) -> int:
    out_dir = _ensure_out_dir(args.out)
    report = validate_catalog_file(Path(args.catalog))
    (out_dir / "chords_validate_latest.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return 0 if report.get("ok") is True else 2


def cmd_passport_observe_max(args: argparse.Namespace) -> int:
    out_dir = _ensure_out_dir(args.out)
    try:
        observe_path = Path(args.observe_path) if args.observe_path else None
        samples, _ = _collect_observe_samples(
            scenario="baseline",
            observe_source=args.observe_source,
            observe_path=observe_path,
            k8s_namespace=getattr(args, "k8s_namespace", "default"),
            k8s_deployment=getattr(args, "k8s_deployment", "trainer"),
            observe_container=getattr(args, "observe_container", "auto"),
            observe_duration_ms=_parse_duration_ms(getattr(args, "observe_duration", "60s")),
            observe_record_raw_path=None,
            observe_record_raw_mode="w",
            required_path_flag="--observe-path",
            required_source_flag="--observe-source",
        )

        passport, report = build_observe_max_artifacts(
            samples,
            registry=_build_registry(),
        )
        passport_path = out_dir / "passport_observe_max_latest.json"
        report_path = out_dir / "observe_max_latest.json"
        passport_path.write_text(
            json.dumps(passport, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        report_path.write_text(
            json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    except (Exception, SystemExit) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    return 0


def cmd_passport_observe_max_report(args: argparse.Namespace) -> int:
    out_dir = _ensure_out_dir(args.out)
    try:
        observe_path = Path(args.observe_path) if args.observe_path else None
        samples, _ = _collect_observe_samples(
            scenario="baseline",
            observe_source=args.observe_source,
            observe_path=observe_path,
            k8s_namespace=getattr(args, "k8s_namespace", "default"),
            k8s_deployment=getattr(args, "k8s_deployment", "trainer"),
            observe_container=getattr(args, "observe_container", "auto"),
            observe_duration_ms=_parse_duration_ms(getattr(args, "observe_duration", "60s")),
            observe_record_raw_path=None,
            observe_record_raw_mode="w",
            required_path_flag="--observe-path",
            required_source_flag="--observe-source",
        )

        _passport, report = build_observe_max_artifacts(
            samples,
            registry=_build_registry(),
        )
        report_path = out_dir / "observe_max_latest.json"
        report_path.write_text(
            json.dumps(report, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    except (Exception, SystemExit) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    return 0


def _run_k8s_verify(
    plan_path: Path,
    out_dir: Path,
    explain: ExplainLog,
) -> tuple[int, Path | None, dict | None]:
    """Verify k8s plan against cluster (plan-only, no changes)."""
    explain.emit("k8s_verify_start", {"plan": str(plan_path), "out": str(out_dir)})
    started_at = _utc_now()

    if not plan_path.exists():
        explain.emit("k8s_verify_error", {"kind": "not_found", "plan": str(plan_path), "error": "plan file not found"})
        print(f"ERROR: k8s verify plan not found: {plan_path}", file=sys.stderr)
        return 2, None, None

    try:
        raw = plan_path.read_text(encoding="utf-8")
    except Exception as e:
        explain.emit("k8s_verify_error", {"kind": "not_found", "plan": str(plan_path), "error": str(e)})
        print(f"ERROR: k8s verify cannot read plan: {plan_path}: {e}", file=sys.stderr)
        return 2, None, None

    try:
        plan = json.loads(raw)
    except Exception as e:
        explain.emit("k8s_verify_error", {"kind": "invalid_json", "plan": str(plan_path), "error": str(e)})
        print(f"ERROR: k8s verify invalid JSON in plan: {plan_path}: {e}", file=sys.stderr)
        return 2, None, None

    plan_items, _legacy_single_object, shape_error = _extract_k8s_plan_items(plan, command="k8s verify")
    if shape_error:
        msg = shape_error
        explain.emit("k8s_verify_error", {"kind": "invalid_shape", "plan": str(plan_path), "error": msg})
        print(f"ERROR: {msg}", file=sys.stderr)
        return 2, None, None

    assert plan_items is not None
    normalized_plan, validation_error, error_index = _validate_k8s_plan(plan_items)
    if validation_error:
        payload = {"kind": "invalid_item", "plan": str(plan_path), "error": validation_error}
        if error_index is not None:
            payload["index"] = error_index
        explain.emit("k8s_verify_error", payload)
        if error_index is not None:
            print(f"ERROR: invalid plan item at index={error_index}: {validation_error}", file=sys.stderr)
        else:
            print(f"ERROR: invalid plan item: {validation_error}", file=sys.stderr)
        return 2, None, None

    namespaces = sorted({it["namespace"] for it in normalized_plan})
    deployments = sorted({it["name"] for it in normalized_plan})
    objects = _k8s_objects_from_plan(normalized_plan)
    k8s_namespace = namespaces[0] if len(namespaces) == 1 else "mixed"
    k8s_deployment = deployments[0] if len(deployments) == 1 else "mixed"

    ctx_res = _kubectl(["config", "current-context"])
    kubectl_present = ctx_res.get("error") != "not_found"
    kubectl_context = (
        ctx_res["stdout"].strip()
        if ctx_res.get("rc") == 0 and (ctx_res.get("stdout") or "").strip()
        else None
    )

    items_checks: list[dict] = []
    for it in normalized_plan:
        ns = it["namespace"]
        name = it["name"]
        patch = it.get("patch") or {}

        item = {
            "namespace": ns,
            "name": name,
            "object": _k8s_object(ns, name),
            "namespace_exists": False,
            "deployment_exists": False,
            "dry_run": {"attempted": False, "mode": None, "ok": False, "rc": None, "stderr": None},
        }

        if not kubectl_present:
            item["dry_run"]["stderr"] = "kubectl not found"
            items_checks.append(item)
            continue

        ns_res = _kubectl(["get", f"namespace/{ns}", "-o", "name"])
        item["namespace_exists"] = bool(ns_res.get("rc") == 0)

        dep_res = _kubectl(["-n", ns, "get", f"deployment/{name}", "-o", "name"])
        item["deployment_exists"] = bool(dep_res.get("rc") == 0)

        if item["namespace_exists"] and item["deployment_exists"]:
            patch_json = json.dumps(patch, ensure_ascii=False)
            item["dry_run"]["attempted"] = True

            srv = _kubectl(
                [
                    "-n",
                    ns,
                    "patch",
                    f"deployment/{name}",
                    "--type",
                    "merge",
                    "--dry-run=server",
                    "-o",
                    "name",
                    "-p",
                    patch_json,
                ]
            )
            item["dry_run"].update(
                {
                    "mode": "server",
                    "ok": bool(srv.get("rc") == 0),
                    "rc": srv.get("rc"),
                    "stderr": (srv.get("stderr") or "").strip(),
                }
            )

        items_checks.append(item)
        if (
            not item["namespace_exists"]
            or not item["deployment_exists"]
            or not bool(item["dry_run"]["ok"])
        ):
            break

    ok = bool(
        kubectl_present
        and all(x["namespace_exists"] and x["deployment_exists"] and x["dry_run"]["ok"] for x in items_checks)
    )
    verify_blocker = _select_k8s_verify_blocker(
        ok=ok,
        kubectl_present=kubectl_present,
        items_checks=items_checks,
    )
    verify_rbac = _extract_verify_rbac_diagnostics(verify_blocker, items_checks)

    finished_at = _utc_now()
    diagnostics = _collect_k8s_verify_diagnostics(
        k8s_namespaces=namespaces,
        kubectl_present=kubectl_present,
        explain=explain,
    )
    if len(namespaces) == 1:
        auth_patch_scalar = diagnostics.get("auth_can_i_patch_deployments")
        auth_get_scalar = diagnostics.get("auth_can_i_get_deployments")
    else:
        auth_patch_scalar = None
        auth_get_scalar = None
    auth_patch_by_ns = diagnostics.get("auth_can_i_patch_deployments_by_namespace", {})
    auth_get_by_ns = diagnostics.get("auth_can_i_get_deployments_by_namespace", {})
    for item in items_checks:
        ns = item.get("namespace")
        if auth_patch_scalar is not None and len(namespaces) == 1:
            item["auth_can_i_patch_deployments"] = auth_patch_scalar
        else:
            item["auth_can_i_patch_deployments"] = (
                auth_patch_by_ns.get(ns) if isinstance(auth_patch_by_ns, dict) else None
            )
        if auth_get_scalar is not None and len(namespaces) == 1:
            item["auth_can_i_get_deployments"] = auth_get_scalar
        else:
            item["auth_can_i_get_deployments"] = (
                auth_get_by_ns.get(ns) if isinstance(auth_get_by_ns, dict) else None
            )
    report_base = {
        "mode": "plan_only",
        "k8s_plan_path": str(plan_path),
        "k8s_plan_items": len(normalized_plan),
        "k8s_namespace": k8s_namespace,
        "k8s_deployment": k8s_deployment,
        "objects": objects,
        "kubectl_context": kubectl_context,
        "diagnostics": diagnostics,
        "checks": {
            "kubectl_present": kubectl_present,
            "current_context": {
                "ok": bool(ctx_res.get("rc") == 0),
                "rc": ctx_res.get("rc"),
                "stderr": (ctx_res.get("stderr") or "").strip(),
            },
            "items": items_checks,
        },
        "verify_blocker": verify_blocker,
        "ok": ok,
    }
    if verify_rbac is not None:
        _ensure_report_details(report_base)["rbac"] = verify_rbac
    report = _build_report(
        report_base,
        started_at=started_at,
        finished_at=finished_at,
        out_dir=out_dir,
        mode="plan_only",
        apply_requested=False,
        dry_run=True,
    )

    explain.emit("k8s_verify_checked", {"items": len(normalized_plan), "ok": ok})
    report_path = _write_report(
        out_dir=out_dir,
        report=report,
        prefix="k8s_verify",
        latest_name="k8s_verify_latest.json",
    )
    explain.emit("k8s_verify_report", {"path": str(report_path)})

    return 0, report_path, report


def cmd_k8s_verify(args: argparse.Namespace) -> int:
    """Verify k8s plan against cluster (plan-only, no changes)."""
    out_dir = _ensure_out_dir(args.out)
    explain = ExplainLog(out_dir / "explain.jsonl")
    rc, _, _ = _run_k8s_verify(Path(args.plan), out_dir, explain)
    return rc


def cmd_license_verify(args: argparse.Namespace) -> int:
    out_dir = _ensure_out_dir(args.out)
    license_path = _resolve_license_verify_path(args.license)
    verify = verify_license(
        license_path,
        kubectl=os.environ.get("KUBECTL", args.kubectl),
        trust_chain=bool(args.trust_chain),
        issuer_keyset_path=Path(args.issuer_keyset) if args.issuer_keyset else None,
        public_keys_path=Path(args.root_public_keys) if args.root_public_keys else None,
    )
    latest_path = out_dir / "license_verify_latest.json"
    latest_path.write_text(
        json.dumps(verify, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return 0 if verify.get("license_ok") is True else 2


def cmd_k8s_render(args: argparse.Namespace) -> int:
    started_at = _utc_now()
    out_dir = _ensure_out_dir(args.out)
    explain = ExplainLog(out_dir / "explain.jsonl")
    explain.emit("k8s_render_start", {"plan": str(args.plan), "out": str(out_dir)})

    plan_path = Path(args.plan)
    try:
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        error_msg = f"plan file not found: {plan_path}"
        explain.emit(
            "k8s_render_error",
            {"kind": "not_found", "plan": str(plan_path), "error": error_msg},
        )
        print(error_msg, file=sys.stderr)
        return 2
    except json.JSONDecodeError as exc:
        explain.emit(
            "k8s_render_error",
            {"kind": "invalid_json", "plan": str(plan_path), "error": str(exc)},
        )
        print(f"failed to parse plan JSON: {exc}", file=sys.stderr)
        return 2

    if not isinstance(plan, list):
        error_msg = "k8s render expects plan JSON to be a list of items"
        explain.emit(
            "k8s_render_error",
            {"kind": "invalid_shape", "plan": str(plan_path), "error": error_msg},
        )
        print(error_msg, file=sys.stderr)
        return 2

    normalized_plan, validation_error, error_index = _validate_k8s_plan(plan)
    if validation_error:
        explain.emit(
            "k8s_render_error",
            {
                "kind": "invalid_item",
                "plan": str(plan_path),
                "error": validation_error,
                "index": error_index,
            },
        )
        print(validation_error, file=sys.stderr)
        return 2

    namespace = _infer_uniform_value(normalized_plan, "namespace")
    deployment = _infer_uniform_value(normalized_plan, "name")
    k8s_kubectl_plan_path = _write_kubectl_plan(
        out_dir,
        normalized_plan,
        namespace,
        deployment,
    )
    explain.emit(
        "k8s_kubectl_plan_written",
        {"path": str(k8s_kubectl_plan_path), "items": len(normalized_plan)},
    )

    report_base = {
        "k8s_kubectl_plan_path": str(k8s_kubectl_plan_path),
        "k8s_plan_items": len(normalized_plan),
        "k8s_namespace": namespace,
        "k8s_deployment": deployment,
    }
    finished_at = _utc_now()
    report = _build_report(
        report_base,
        started_at=started_at,
        finished_at=finished_at,
        out_dir=out_dir,
        mode="K8S_RENDER",
        apply_requested=False,
        dry_run=True,
    )
    report_path = _write_report(
        out_dir,
        report,
        prefix="k8s_render",
        latest_name="k8s_render_latest.json",
    )
    explain.emit("k8s_render_report", {"path": str(report_path)})
    return 0


def _run_k8s_apply(
    plan_path: Path,
    out_dir: Path,
    explain: ExplainLog,
    *,
    force: bool,
    license_path: Path | None,
) -> tuple[int, Path | None, dict | None]:
    pro_cli_ext = _load_pro_cli_ext()
    if pro_cli_ext is not None and hasattr(pro_cli_ext, "run_k8s_apply"):
        return pro_cli_ext.run_k8s_apply(
            plan_path,
            out_dir,
            explain,
            force=force,
            license_path=license_path,
        )

    report_path = _write_pro_required_k8s_apply_artifacts(
        out_dir=out_dir,
        plan_path=plan_path,
    )
    report: dict | None = None
    try:
        loaded = json.loads(report_path.read_text(encoding="utf-8"))
        if isinstance(loaded, dict):
            report = loaded
    except Exception:
        report = None
    return 2, report_path, report


def cmd_k8s_apply(args: argparse.Namespace) -> int:
    kill_switch = _evaluate_kill_switch_signal()
    if bool(kill_switch.get("active")):
        out_dir = _ensure_out_dir(args.out)
        _write_pro_required_k8s_apply_artifacts(
            out_dir=out_dir,
            plan_path=Path(args.plan),
            block_reason=_KILL_SWITCH_BLOCK_REASON,
            block_details={
                "kill_switch_active": True,
                "kill_switch_signal": (
                    str(kill_switch.get("signal")) if kill_switch.get("signal") else None
                ),
            },
        )
        _emit_policy_bundle_latest(
            out_dir,
            policy_id="external_plan",
            policy_version="v1",
            policy_params={},
        )
        _emit_kill_switch_error()
        return 2

    pro_cli_ext = _load_pro_cli_ext()
    if pro_cli_ext is not None and hasattr(pro_cli_ext, "cmd_k8s_apply"):
        return int(pro_cli_ext.cmd_k8s_apply(args))

    out_dir = _ensure_out_dir(args.out)
    _write_pro_required_k8s_apply_artifacts(out_dir=out_dir, plan_path=Path(args.plan))
    _emit_policy_bundle_latest(
        out_dir,
        policy_id="external_plan",
        policy_version="v1",
        policy_params={},
    )
    return _require_pro("k8s apply")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mk")
    parser.add_argument("--version", action="version", version=f"modekeeper {MK_VERSION}")

    sub = parser.add_subparsers(dest="command", required=True)

    doctor = sub.add_parser("doctor", help="Check local onboarding prerequisites")
    doctor.set_defaults(func=cmd_doctor)

    quickstart = sub.add_parser(
        "quickstart",
        help="Run customer-ready read-only onboarding flow",
    )
    quickstart.add_argument(
        "--out",
        help="Output directory (default: ./report/quickstart_<UTC ts>/, ts=YYYYMMDDTHHMMSSZ)",
    )
    quickstart.add_argument("--k8s-namespace", default="default", help="K8s namespace")
    quickstart.add_argument("--k8s-deployment", default="trainer", help="K8s deployment")
    quickstart.add_argument("--scenario", default="drift", help="Synthetic scenario")
    quickstart.add_argument(
        "--observe-source",
        default="synthetic",
        choices=["synthetic", "file", "k8s", "k8s-logs"],
        help="Telemetry source for closed-loop signals",
    )
    quickstart.add_argument(
        "--observe-path",
        help="Path to metrics file for observe-source=file",
    )
    quickstart.add_argument(
        "--observe-duration",
        default="60s",
        help="Observe duration (e.g. 30s, 2m) for synthetic/k8s sources",
    )
    quickstart.add_argument(
        "--observe-container",
        default="auto",
        help="K8s container name",
    )
    quickstart.add_argument(
        "--policy",
        default="chord",
        choices=["chord", "scalar"],
        help="Policy selector for action proposal",
    )
    quickstart.set_defaults(func=cmd_quickstart)

    preflight = sub.add_parser("preflight", help="Buyer-safe preflight report (read-only)")
    preflight.add_argument("--out", required=True, help="Output directory")
    preflight.add_argument("--inputs-root", help=argparse.SUPPRESS)
    preflight.set_defaults(func=cmd_preflight)

    eval_cmd = sub.add_parser("eval", help="Customer-safe evaluation (read-only)")
    eval_cmd.set_defaults(func=cmd_eval)
    eval_cmd.add_argument("--out", help="Output directory for top-level eval report")
    eval_cmd.add_argument("--inputs-root", help=argparse.SUPPRESS)
    eval_sub = eval_cmd.add_subparsers(dest="subcommand", required=False)
    eval_file = eval_sub.add_parser("file", help="Evaluate from file telemetry (read-only)")
    eval_file.add_argument("--path", required=True, help="Path to metrics file (.jsonl or .csv)")
    eval_file.add_argument(
        "--policy",
        default="chord",
        choices=["chord", "scalar"],
        help="Policy selector for action proposal",
    )
    eval_file.add_argument("--out", default="report", help="Output directory")
    eval_file.set_defaults(func=cmd_eval_file)

    eval_k8s = eval_sub.add_parser("k8s", help="Evaluate from k8s telemetry (read-only)")
    eval_k8s.add_argument("--k8s-namespace", default="default", help="K8s namespace")
    eval_k8s.add_argument("--k8s-deployment", default="trainer", help="K8s deployment")
    eval_k8s.add_argument("--container", default="auto", help="K8s container name")
    eval_k8s.add_argument(
        "--observe-duration",
        default="60s",
        help="Observe duration (e.g. 30s, 2m)",
    )
    eval_k8s.add_argument(
        "--policy",
        default="chord",
        choices=["chord", "scalar"],
        help="Policy selector for action proposal",
    )
    eval_k8s.add_argument("--out", default="report", help="Output directory")
    eval_k8s.set_defaults(func=cmd_eval_k8s)

    observe = sub.add_parser("observe", help="Run OBSERVE_ONLY mode")
    observe.add_argument(
        "--duration",
        default="10m",
        help="e.g. 1.5s, 250ms, 10m (no suffix = seconds)",
    )
    observe.add_argument(
        "--source",
        default="synthetic",
        choices=["synthetic", "file", "k8s", "k8s-logs"],
        help="Telemetry source",
    )
    observe.add_argument("--path", help="Path to metrics file (.jsonl or .csv)")
    observe.add_argument(
        "--record-raw",
        help="Write raw observe stream to PATH (one line per record)",
    )
    observe.add_argument("--k8s-namespace", default="default", help="K8s namespace")
    observe.add_argument("--k8s-deployment", default="trainer", help="K8s deployment")
    observe.add_argument("--container", default="auto", help="K8s container name")
    observe.add_argument("--k8s-pod", default=None, help="K8s pod name")
    observe.add_argument("--out", default="report", help="Output directory")
    observe.set_defaults(func=cmd_observe)

    closed = sub.add_parser("closed-loop", help="Run CLOSED_LOOP mode")
    closed_sub = closed.add_subparsers(dest="subcommand", required=True)
    closed_run = closed_sub.add_parser("run", help="Run closed-loop once")
    closed_run.add_argument("--out", default="report", help="Output directory")
    closed_run.add_argument("--scenario", default="drift", help="Synthetic scenario")
    closed_run.add_argument("--k8s-namespace", default="default", help="K8s namespace")
    closed_run.add_argument("--k8s-deployment", default="trainer", help="K8s deployment")
    closed_run.add_argument(
        "--observe-source",
        default="synthetic",
        choices=["synthetic", "file", "k8s", "k8s-logs"],
        help="Telemetry source for closed-loop signals",
    )
    closed_run.add_argument("--observe-path", help="Path to metrics file for observe-source=file")
    closed_run.add_argument(
        "--observe-record-raw",
        help="Write raw observe stream to PATH (one line per record)",
    )
    closed_run.add_argument(
        "--observe-duration",
        default="60s",
        help="Observe duration (e.g. 30s, 2m) for synthetic/k8s sources",
    )
    closed_run.add_argument(
        "--policy",
        default="chord",
        choices=["chord", "scalar"],
        help="Policy selector for action proposal",
    )
    closed_run.add_argument("--observe-container", default="auto", help="K8s container name")
    closed_run.add_argument(
        "--cooldown-s",
        type=int,
        default=30,
        help="Minimum cooldown between safety changes in seconds",
    )
    closed_run.add_argument(
        "--max-delta-per-step",
        type=int,
        default=0,
        help="Maximum allowed |clamped_target-current| per action (0=off)",
    )
    closed_run.add_argument(
        "--approve-advanced",
        action="store_true",
        help="Allow applying advanced actions",
    )
    closed_run.add_argument(
        "--license-path",
        help="License path override for apply gate lookup",
    )
    apply_group = closed_run.add_mutually_exclusive_group()
    apply_group.add_argument("--dry-run", action="store_true", help="Do not apply")
    apply_group.add_argument("--apply", action="store_true", help="Apply actions")
    closed_run.set_defaults(func=cmd_closed_loop)

    closed_watch = closed_sub.add_parser("watch", help="Run closed-loop controller loop")
    closed_watch.add_argument("--out", required=True, help="Output directory")
    closed_watch.add_argument("--scenario", required=True, help="Synthetic scenario")
    closed_watch.add_argument("--k8s-namespace", default="default", help="K8s namespace")
    closed_watch.add_argument("--k8s-deployment", default="trainer", help="K8s deployment")
    closed_watch.add_argument(
        "--observe-source",
        default="synthetic",
        choices=["synthetic", "file", "k8s", "k8s-logs"],
        help="Telemetry source for closed-loop signals",
    )
    closed_watch.add_argument("--observe-path", help="Path to metrics file for observe-source=file")
    closed_watch.add_argument(
        "--observe-record-raw",
        help="Write raw observe stream to PATH (one line per record)",
    )
    closed_watch.add_argument(
        "--observe-duration",
        default="60s",
        help="Observe duration (e.g. 30s, 2m) for synthetic/k8s sources",
    )
    closed_watch.add_argument(
        "--policy",
        default="chord",
        choices=["chord", "scalar"],
        help="Policy selector for action proposal",
    )
    closed_watch.add_argument("--observe-container", default="auto", help="K8s container name")
    closed_watch.add_argument(
        "--cooldown-s",
        type=int,
        default=30,
        help="Minimum cooldown between safety changes in seconds",
    )
    closed_watch.add_argument(
        "--max-delta-per-step",
        type=int,
        default=0,
        help="Maximum allowed |clamped_target-current| per action (0=off)",
    )
    closed_watch.add_argument(
        "--approve-advanced",
        action="store_true",
        help="Allow applying advanced actions",
    )
    closed_watch.add_argument(
        "--license-path",
        help="License path override for apply gate lookup",
    )
    closed_watch.add_argument(
        "--iterations",
        type=int,
        default=0,
        help="Stop after N iterations (0=forever)",
    )

    closed_watch.add_argument(
        "--interval",
        default=_parse_duration_ms("30s"),
        type=_parse_duration_ms,
        help="Sleep between iterations (e.g. 30s, 250ms)",
    )
    closed_watch.add_argument(
        "--max-iterations",
        type=int,
        default=None,
        help="Stop after N iterations (default: run until stopped)",
    )
    watch_apply_group = closed_watch.add_mutually_exclusive_group()
    watch_apply_group.add_argument("--dry-run", action="store_true", help="Do not apply")
    watch_apply_group.add_argument("--apply", action="store_true", help="Apply actions")
    closed_watch.set_defaults(func=cmd_closed_loop_watch)

    watch = sub.add_parser("watch", help="Buyer-safe watch summary artifact (read-only)")
    watch.add_argument("--out", required=True, help="Output directory")
    watch.add_argument(
        "--duration",
        type=int,
        default=60,
        help="Synthetic watch duration in seconds for rollup metadata",
    )
    watch.add_argument("--inputs-root", help=argparse.SUPPRESS)
    watch.set_defaults(func=cmd_watch)

    demo = sub.add_parser("demo", help="Run demo scenarios")
    demo_sub = demo.add_subparsers(dest="subcommand", required=True)
    demo_run = demo_sub.add_parser("run", help="Run a demo scenario")
    demo_run.add_argument("--scenario", default="drift", help="Scenario name")
    demo_run.add_argument("--out", default="report", help="Output directory")
    demo_run.set_defaults(func=cmd_demo)
    demo_mk068 = demo_sub.add_parser("mk068", help="Run deterministic MK-068 demo scenario")
    demo_mk068.add_argument("--out", default="report", help="Output directory")
    demo_mk068.set_defaults(func=cmd_demo_mk068)

    fleet = sub.add_parser("fleet", help="Fleet utilities")
    fleet_sub = fleet.add_subparsers(dest="subcommand", required=True)
    fleet_inventory = fleet_sub.add_parser(
        "inventory",
        help="Collect multi-cluster inventory (skeleton)",
    )
    fleet_contexts = fleet_inventory.add_mutually_exclusive_group()
    fleet_contexts.add_argument(
        "--contexts",
        help="Comma-separated kube contexts, e.g. ctx-a,ctx-b",
    )
    fleet_contexts.add_argument(
        "--context",
        action="append",
        help="Kube context (repeat flag for multiple contexts)",
    )
    fleet_inventory.add_argument(
        "--out",
        default="report/_inventory",
        help="Output directory",
    )
    fleet_inventory.set_defaults(func=cmd_fleet_inventory)
    fleet_policy = fleet_sub.add_parser(
        "policy",
        help="Collect policy propagation report (skeleton)",
    )
    fleet_policy.add_argument(
        "--policy",
        required=True,
        help="Policy reference (template name or JSON file path)",
    )
    fleet_policy_contexts = fleet_policy.add_mutually_exclusive_group()
    fleet_policy_contexts.add_argument(
        "--contexts",
        help="Comma-separated kube contexts, e.g. ctx-a,ctx-b",
    )
    fleet_policy_contexts.add_argument(
        "--context",
        action="append",
        help="Kube context (repeat flag for multiple contexts)",
    )
    fleet_policy.add_argument(
        "--out",
        default="report/_policy_propagation",
        help="Output directory",
    )
    fleet_policy.set_defaults(func=cmd_fleet_policy)

    roi = sub.add_parser("roi", help="ROI reports")
    roi.set_defaults(func=cmd_roi)
    roi.add_argument("--out", help="Output directory for top-level roi report")
    roi.add_argument("--inputs-root", help=argparse.SUPPRESS)
    roi_sub = roi.add_subparsers(dest="subcommand", required=False)
    roi_mk074 = roi_sub.add_parser("mk074", help="Build MK-074 before/after ROI report")
    roi_mk074.add_argument(
        "--observe-source",
        required=True,
        choices=["file", "k8s", "k8s-logs"],
        help="Telemetry source for ROI replay",
    )
    roi_mk074.add_argument(
        "--observe-path",
        help="Path to metrics file for observe-source=file",
    )
    roi_mk074.add_argument(
        "--k8s-namespace",
        default="default",
        help="K8s namespace for observe-source=k8s",
    )
    roi_mk074.add_argument(
        "--k8s-deployment",
        default="trainer",
        help="K8s deployment for observe-source=k8s",
    )
    roi_mk074.add_argument(
        "--observe-container",
        default="auto",
        help="K8s container name for observe-source=k8s",
    )
    roi_mk074.add_argument(
        "--observe-duration",
        default="60s",
        help="Observe duration for observe-source=k8s",
    )
    roi_mk074.add_argument("--out", required=True, help="Output directory")
    roi_mk074.set_defaults(func=cmd_roi_mk074)
    roi_estimate = roi_sub.add_parser("estimate", help="Build non-actionable free ROI estimate")
    roi_estimate.add_argument(
        "--observe-source",
        required=True,
        choices=["file"],
        help="Telemetry source for ROI estimate",
    )
    roi_estimate.add_argument(
        "--observe-path",
        required=True,
        help="Path to metrics file for observe-source=file",
    )
    roi_estimate.add_argument(
        "--out",
        default="report/_roi_estimate",
        help="Output directory",
    )
    roi_estimate.set_defaults(func=cmd_roi_estimate)
    roi_report = roi_sub.add_parser(
        "report",
        help="Build investor-grade ROI/value summary from preflight/eval/watch artifacts",
    )
    roi_report.add_argument(
        "--preflight",
        default="report/preflight/preflight_latest.json",
        help="Path to preflight_latest.json",
    )
    roi_report.add_argument(
        "--eval",
        default="report/eval_k8s/eval_latest.json",
        help="Path to eval_latest.json",
    )
    roi_report.add_argument(
        "--watch",
        default="report/watch_k8s/watch_latest.json",
        help="Path to watch_latest.json",
    )
    roi_report.add_argument(
        "--out",
        default="report/roi",
        help="Output directory",
    )
    roi_report.set_defaults(func=cmd_roi_report)

    export_cmd = sub.add_parser("export", help="Offline-first artifacts export")
    export_sub = export_cmd.add_subparsers(dest="subcommand", required=True)
    export_bundle = export_sub.add_parser(
        "bundle",
        help="Build shareable bundle (manifest + tar.gz) from latest artifacts",
    )
    export_bundle.add_argument(
        "--in",
        dest="input_dir",
        default="report",
        help="Input root with latest artifacts",
    )
    export_bundle.add_argument(
        "--out",
        default="report/bundle",
        help="Output directory",
    )
    export_bundle.set_defaults(func=cmd_export_bundle)

    chords = sub.add_parser("chords", help="Chord catalog utilities")
    chords_sub = chords.add_subparsers(dest="subcommand", required=True)
    chords_validate = chords_sub.add_parser("validate", help="Validate chord catalog JSON")
    chords_validate.add_argument("--catalog", required=True, help="Path to chord catalog JSON")
    chords_validate.add_argument(
        "--out",
        default="report/_chords_validate",
        help="Output directory",
    )
    chords_validate.set_defaults(func=cmd_chords_validate)

    passport = sub.add_parser("passport", help="Passport templates and validation")
    passport_sub = passport.add_subparsers(dest="subcommand", required=True)
    passport_templates = passport_sub.add_parser("templates", help="List built-in passport templates")
    passport_templates.set_defaults(func=cmd_passport_templates)
    passport_show = passport_sub.add_parser("show", help="Print a built-in passport template")
    passport_show.add_argument("--template", required=True, help="Template name")
    passport_show.set_defaults(func=cmd_passport_show)
    passport_validate = passport_sub.add_parser("validate", help="Validate passport.v0 JSON file")
    passport_validate.add_argument("--file", required=True, help="Path to passport JSON file")
    passport_validate.set_defaults(func=cmd_passport_validate)
    passport_observe_max = passport_sub.add_parser(
        "observe-max",
        help="Build free observe_max passport and recommendation report",
    )
    passport_observe_max.add_argument(
        "--observe-source",
        required=True,
        choices=["file", "k8s", "k8s-logs"],
        help="Telemetry source for observe_max calibration",
    )
    passport_observe_max.add_argument(
        "--observe-path",
        help="Path to metrics file for observe-source=file",
    )
    passport_observe_max.add_argument(
        "--k8s-namespace",
        default="default",
        help="K8s namespace for observe-source=k8s",
    )
    passport_observe_max.add_argument(
        "--k8s-deployment",
        default="trainer",
        help="K8s deployment for observe-source=k8s",
    )
    passport_observe_max.add_argument(
        "--observe-container",
        default="auto",
        help="K8s container name for observe-source=k8s",
    )
    passport_observe_max.add_argument(
        "--observe-duration",
        default="60s",
        help="Observe duration for observe-source=k8s",
    )
    passport_observe_max.add_argument("--out", required=True, help="Output directory")
    passport_observe_max.set_defaults(func=cmd_passport_observe_max)
    passport_observe_max_report = passport_sub.add_parser(
        "observe-max-report",
        help="Build free observe_max redacted report only",
    )
    passport_observe_max_report.add_argument(
        "--observe-source",
        required=True,
        choices=["file", "k8s", "k8s-logs"],
        help="Telemetry source for observe_max calibration",
    )
    passport_observe_max_report.add_argument(
        "--observe-path",
        help="Path to metrics file for observe-source=file",
    )
    passport_observe_max_report.add_argument(
        "--k8s-namespace",
        default="default",
        help="K8s namespace for observe-source=k8s",
    )
    passport_observe_max_report.add_argument(
        "--k8s-deployment",
        default="trainer",
        help="K8s deployment for observe-source=k8s",
    )
    passport_observe_max_report.add_argument(
        "--observe-container",
        default="auto",
        help="K8s container name for observe-source=k8s",
    )
    passport_observe_max_report.add_argument(
        "--observe-duration",
        default="60s",
        help="Observe duration for observe-source=k8s",
    )
    passport_observe_max_report.add_argument("--out", required=True, help="Output directory")
    passport_observe_max_report.set_defaults(func=cmd_passport_observe_max_report)

    license_cmd = sub.add_parser("license", help="License utilities")
    license_sub = license_cmd.add_subparsers(dest="subcommand", required=True)
    license_verify = license_sub.add_parser(
        "verify",
        help="Verify license.v1 JSON",
        description=(
            "Verify license.v1 JSON. Defaults: --license "
            "MODEKEEPER_LICENSE_PATH, else ${HOME}/.config/modekeeper/license.json. "
            "Public keys: MODEKEEPER_LICENSE_PUBLIC_KEYS_PATH, else "
            "${HOME}/.config/modekeeper/license_public_keys.json if present, "
            "else built-in keyring."
        ),
    )
    license_verify.add_argument(
        "--license",
        help=(
            "Path to license JSON (default: MODEKEEPER_LICENSE_PATH, "
            "else ${HOME}/.config/modekeeper/license.json)"
        ),
    )
    license_verify.add_argument(
        "--trust-chain",
        action="store_true",
        help=(
            "Enable trust-chain verification: root public key allowlist verifies "
            "issuer keyset signature, then issuer keys verify license"
        ),
    )
    license_verify.add_argument(
        "--issuer-keyset",
        help=(
            "Path to issuer keyset JSON (required with --trust-chain). "
            "Expected schema: issuer_keyset.v1"
        ),
    )
    license_verify.add_argument(
        "--root-public-keys",
        help=(
            "Path to root public key allowlist JSON map {kid->pubkey_b64_raw32}. "
            "Without --trust-chain this path acts as a direct keyring override."
        ),
    )
    license_verify.add_argument("--out", default="report/_license_verify", help="Output directory")
    license_verify.add_argument(
        "--kubectl",
        default="kubectl",
        help="kubectl binary for kube-context binding checks",
    )
    license_verify.set_defaults(func=cmd_license_verify)

    k8s = sub.add_parser("k8s", help="K8s utilities")
    k8s_sub = k8s.add_subparsers(dest="subcommand", required=True)
    k8s_render = k8s_sub.add_parser("render", help="Render kubectl plan script")
    k8s_render.add_argument("--plan", required=True, help="Path to k8s plan JSON")
    k8s_render.add_argument("--out", default="report", help="Output directory")
    k8s_render.set_defaults(func=cmd_k8s_render)

    k8s_verify = k8s_sub.add_parser("verify", help="Verify k8s plan against cluster (no changes)")
    k8s_verify.add_argument("--plan", required=True, help="Path to k8s plan JSON")
    k8s_verify.add_argument("--out", default="report", help="Output directory")
    k8s_verify.set_defaults(func=cmd_k8s_verify)

    k8s_preflight = k8s_sub.add_parser(
        "preflight", help="Customer-safe k8s preflight checks (read-only)"
    )
    k8s_preflight.add_argument("--k8s-namespace", default="default", help="K8s namespace")
    k8s_preflight.add_argument("--k8s-deployment", default="trainer", help="K8s deployment")
    k8s_preflight.add_argument("--out", default="report/preflight", help="Output directory")
    k8s_preflight.set_defaults(func=cmd_k8s_preflight)

    k8s_apply = k8s_sub.add_parser("apply", help="Apply k8s plan (paid, hard-blocked)")
    k8s_apply.add_argument("--plan", required=True, help="Path to k8s plan JSON")
    k8s_apply.add_argument("--out", default="report", help="Output directory")
    k8s_apply.add_argument(
        "--force",
        action="store_true",
        help="Reserved flag (verify_ok=true is still required)",
    )
    k8s_apply.add_argument(
        "--license-path",
        help="License path override for apply gate lookup",
    )
    k8s_apply.set_defaults(func=cmd_k8s_apply)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
