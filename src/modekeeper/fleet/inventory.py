"""Fleet inventory collection."""

from __future__ import annotations

import json
import subprocess


def _run_kubectl_json(kubectl: str, args: list[str]) -> tuple[bool, dict, int]:
    try:
        cp = subprocess.run(
            [kubectl, *args],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return False, {}, 127
    if cp.returncode != 0:
        return False, {}, int(cp.returncode)
    try:
        payload = json.loads(cp.stdout or "{}")
    except json.JSONDecodeError:
        return False, {}, 1
    if not isinstance(payload, dict):
        return False, {}, 1
    return True, payload, 0


def _get_current_context(kubectl: str) -> tuple[str | None, int]:
    try:
        cp = subprocess.run(
            [kubectl, "config", "current-context"],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return None, 127
    if cp.returncode != 0:
        return None, int(cp.returncode)
    context = (cp.stdout or "").strip()
    if not context:
        return None, 1
    return context, 0


def _normalize_contexts(contexts: list[str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for raw in contexts:
        value = raw.strip()
        if not value or value in seen:
            continue
        seen.add(value)
        normalized.append(value)
    return normalized


def _collect_context_inventory(context: str, kubectl: str) -> dict:
    base = {
        "context": context,
        "namespaces": [],
        "deployments": [],
    }
    ok_ns, ns_payload, ns_rc = _run_kubectl_json(
        kubectl,
        ["--context", context, "get", "namespaces", "-o", "json"],
    )
    if not ok_ns:
        base["error"] = {"reason": "kubectl_failed", "rc": ns_rc}
        return base

    ok_dep, dep_payload, dep_rc = _run_kubectl_json(
        kubectl,
        ["--context", context, "get", "deployments", "-A", "-o", "json"],
    )
    if not ok_dep:
        base["error"] = {"reason": "kubectl_failed", "rc": dep_rc}
        return base

    namespaces: list[str] = []
    for item in ns_payload.get("items", []):
        if not isinstance(item, dict):
            continue
        metadata = item.get("metadata")
        if not isinstance(metadata, dict):
            continue
        name = metadata.get("name")
        if isinstance(name, str) and name.strip():
            namespaces.append(name.strip())

    deployments: list[dict[str, str]] = []
    for item in dep_payload.get("items", []):
        if not isinstance(item, dict):
            continue
        metadata = item.get("metadata")
        if not isinstance(metadata, dict):
            continue
        name = metadata.get("name")
        namespace = metadata.get("namespace")
        if (
            isinstance(name, str)
            and name.strip()
            and isinstance(namespace, str)
            and namespace.strip()
        ):
            deployments.append(
                {"namespace": namespace.strip(), "name": name.strip()}
            )

    base["namespaces"] = sorted(set(namespaces))
    base["deployments"] = sorted(
        deployments,
        key=lambda item: (item["namespace"], item["name"]),
    )
    return base


def collect_inventory(contexts: list[str] | None, kubectl: str = "kubectl") -> dict:
    target_contexts: list[str]
    if contexts:
        target_contexts = _normalize_contexts(contexts)
    else:
        current, rc = _get_current_context(kubectl)
        if current:
            target_contexts = [current]
        else:
            return {
                "schema": "inventory.v0",
                "contexts": [
                    {
                        "context": "current",
                        "namespaces": [],
                        "deployments": [],
                        "error": {"reason": "kubectl_failed", "rc": rc},
                    }
                ],
            }

    context_reports = [
        _collect_context_inventory(context=context, kubectl=kubectl)
        for context in target_contexts
    ]
    return {
        "schema": "inventory.v0",
        "contexts": context_reports,
    }

