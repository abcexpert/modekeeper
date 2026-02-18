"""Fleet policy propagation skeleton (plan-only)."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path


_POLICY_REF_ANNOTATION = "modekeeper/policy.ref"
_POLICY_VERSION_ANNOTATION = "modekeeper/policy.version"


def _read_policy_bytes(policy_ref: str) -> bytes:
    if "/" in policy_ref or policy_ref.endswith(".json"):
        return Path(policy_ref).read_bytes()
    templates_dir = Path(__file__).resolve().parents[1] / "passports" / "templates"
    return (templates_dir / f"{policy_ref}.json").read_bytes()


def compute_policy_version(policy_ref: str) -> dict:
    payload = _read_policy_bytes(policy_ref)
    sha256 = hashlib.sha256(payload).hexdigest()
    return {
        "policy_ref": policy_ref,
        "sha256": sha256,
        "version_short": sha256[:12],
    }


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
    normalized: set[str] = set()
    for raw in contexts:
        value = raw.strip()
        if value:
            normalized.add(value)
    return sorted(normalized)


def _collect_context_deployments(
    context: str,
    policy_ref: str,
    desired_version: str,
    kubectl: str,
) -> dict:
    base = {
        "context": context,
        "deployments": [],
    }
    ok_dep, dep_payload, dep_rc = _run_kubectl_json(
        kubectl,
        ["--context", context, "get", "deployments", "-A", "-o", "json"],
    )
    if not ok_dep:
        base["error"] = {"reason": "kubectl_failed", "rc": dep_rc}
        return base

    deployments: list[dict] = []
    for item in dep_payload.get("items", []):
        if not isinstance(item, dict):
            continue
        metadata = item.get("metadata")
        if not isinstance(metadata, dict):
            continue
        name = metadata.get("name")
        namespace = metadata.get("namespace")
        if not (isinstance(name, str) and name.strip() and isinstance(namespace, str) and namespace.strip()):
            continue

        annotations = metadata.get("annotations")
        if not isinstance(annotations, dict):
            annotations = {}
        current_policy_ref = annotations.get(_POLICY_REF_ANNOTATION)
        current_policy_version = annotations.get(_POLICY_VERSION_ANNOTATION)
        if not isinstance(current_policy_ref, str):
            current_policy_ref = None
        if not isinstance(current_policy_version, str):
            current_policy_version = None

        deployments.append(
            {
                "namespace": namespace.strip(),
                "name": name.strip(),
                "current_policy_ref": current_policy_ref,
                "current_policy_version": current_policy_version,
                "desired_policy_ref": policy_ref,
                "desired_policy_version": desired_version,
                "change_required": (
                    current_policy_ref != policy_ref
                    or current_policy_version != desired_version
                ),
                "rollback_policy_ref": current_policy_ref,
                "rollback_policy_version": current_policy_version,
            }
        )

    base["deployments"] = sorted(
        deployments,
        key=lambda item: (item["namespace"], item["name"]),
    )
    return base


def collect_policy_propagation(
    contexts: list[str] | None,
    policy_ref: str,
    kubectl: str = "kubectl",
) -> dict:
    desired_policy = compute_policy_version(policy_ref)

    target_contexts: list[str]
    if contexts:
        target_contexts = _normalize_contexts(contexts)
    else:
        current, rc = _get_current_context(kubectl)
        if current:
            target_contexts = [current]
        else:
            return {
                "schema": "policy_propagation.v0",
                "desired_policy": desired_policy,
                "contexts": [
                    {
                        "context": "current",
                        "deployments": [],
                        "error": {"reason": "kubectl_failed", "rc": rc},
                    }
                ],
            }

    context_reports = [
        _collect_context_deployments(
            context=context,
            policy_ref=desired_policy["policy_ref"],
            desired_version=desired_policy["version_short"],
            kubectl=kubectl,
        )
        for context in sorted(target_contexts)
    ]
    return {
        "schema": "policy_propagation.v0",
        "desired_policy": desired_policy,
        "contexts": context_reports,
    }
