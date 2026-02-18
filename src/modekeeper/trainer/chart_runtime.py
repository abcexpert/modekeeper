"""Minimal in-cluster trainer runtime for Helm chart e2e."""

from __future__ import annotations

import json
import os
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request

_DEFAULT_LOOP_INTERVAL_S = 2.0
_DEFAULT_SA_DIR = "/var/run/secrets/kubernetes.io/serviceaccount"
_KNOB_PREFIX = "modekeeper/knob."


def _to_positive_float(value: str | None, default: float) -> float:
    if value is None:
        return default
    try:
        parsed = float(str(value).strip())
    except (TypeError, ValueError):
        return default
    return parsed if parsed > 0 else default


def _read_text(path: str) -> str:
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read().strip()


def _discover_pod_ref() -> tuple[str, str]:
    pod_name = (os.environ.get("MODEKEEPER_POD_NAME") or os.environ.get("HOSTNAME") or "").strip()
    if not pod_name:
        raise RuntimeError("pod name is unknown (set HOSTNAME or MODEKEEPER_POD_NAME)")

    namespace = os.environ.get("MODEKEEPER_POD_NAMESPACE")
    if namespace is None:
        ns_path = os.environ.get("MODEKEEPER_SA_NAMESPACE_FILE", f"{_DEFAULT_SA_DIR}/namespace")
        namespace = _read_text(ns_path)
    namespace = namespace.strip()
    if not namespace:
        raise RuntimeError("pod namespace is empty")
    return pod_name, namespace


def _kube_api_url(namespace: str, pod_name: str) -> str:
    host = (os.environ.get("KUBERNETES_SERVICE_HOST") or "kubernetes.default.svc").strip()
    port = (
        os.environ.get("KUBERNETES_SERVICE_PORT_HTTPS")
        or os.environ.get("KUBERNETES_SERVICE_PORT")
        or "443"
    ).strip()
    ns_q = urllib.parse.quote(namespace, safe="")
    pod_q = urllib.parse.quote(pod_name, safe="")
    return f"https://{host}:{port}/api/v1/namespaces/{ns_q}/pods/{pod_q}"


def _fetch_pod(pod_name: str, namespace: str) -> dict:
    token_path = os.environ.get("MODEKEEPER_SA_TOKEN_FILE", f"{_DEFAULT_SA_DIR}/token")
    ca_path = os.environ.get("MODEKEEPER_SA_CA_FILE", f"{_DEFAULT_SA_DIR}/ca.crt")
    timeout_s = _to_positive_float(os.environ.get("MODEKEEPER_API_TIMEOUT_S"), default=5.0)

    token = _read_text(token_path)
    if not token:
        raise RuntimeError(f"serviceaccount token is empty ({token_path})")

    request = urllib.request.Request(
        _kube_api_url(namespace, pod_name),
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
    )
    context = ssl.create_default_context(cafile=ca_path)
    try:
        with urllib.request.urlopen(request, context=context, timeout=timeout_s) as response:
            status = getattr(response, "status", None)
            if status != 200:
                raise RuntimeError(f"unexpected status code: {status}")
            payload = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        body = ""
        try:
            body = exc.read().decode("utf-8", errors="replace")
        except Exception:
            body = ""
        message = body.strip().replace("\n", " ")
        if len(message) > 240:
            message = f"{message[:240]}..."
        raise RuntimeError(f"http {exc.code} {exc.reason}: {message}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"url error: {exc.reason}") from exc
    except OSError as exc:
        raise RuntimeError(f"connection error: {exc}") from exc

    try:
        data = json.loads(payload)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"invalid pod json: {exc}") from exc
    if not isinstance(data, dict):
        raise RuntimeError("invalid pod json payload shape")
    return data


def _knob_lines(pod_obj: dict, prefix: str = _KNOB_PREFIX) -> list[str]:
    metadata = pod_obj.get("metadata")
    if not isinstance(metadata, dict):
        return []
    annotations = metadata.get("annotations")
    if not isinstance(annotations, dict):
        return []

    lines: list[str] = []
    for key, value in annotations.items():
        if isinstance(key, str) and key.startswith(prefix):
            lines.append(f"{key}={'' if value is None else str(value)}")
    return sorted(lines)


def main() -> int:
    loop_interval_s = _to_positive_float(
        os.environ.get("MODEKEEPER_LOOP_INTERVAL_S"),
        default=_DEFAULT_LOOP_INTERVAL_S,
    )

    while True:
        pod_name = "<unknown>"
        namespace = "<unknown>"
        try:
            pod_name, namespace = _discover_pod_ref()
            pod_obj = _fetch_pod(pod_name=pod_name, namespace=namespace)
            knob_lines = _knob_lines(pod_obj)
            if knob_lines:
                for line in knob_lines:
                    print(line, flush=True)
            else:
                print("modekeeper/knob.none=true", flush=True)
        except Exception as exc:
            print(
                f"ERROR modekeeper trainer chart pod-read pod={pod_name} namespace={namespace}: {exc}",
                flush=True,
            )
        time.sleep(loop_interval_s)


if __name__ == "__main__":
    raise SystemExit(main())
