import json
import os
import subprocess
from pathlib import Path


def _run(mk: Path, args: list[str], env: dict | None = None) -> subprocess.CompletedProcess[str]:
    e = os.environ.copy()
    if env:
        e.update(env)
    return subprocess.run([str(mk), *args], text=True, capture_output=True, env=e)


def _assert_diagnostics_keys(data: dict) -> None:
    diagnostics = data.get("diagnostics")
    assert isinstance(diagnostics, dict)
    assert "kubectl_version" in diagnostics
    assert "server_version" in diagnostics
    assert "auth_can_i_patch_deployments" in diagnostics
    assert "auth_can_i_get_deployments" in diagnostics
    assert "auth_can_i_patch_deployments_by_namespace" in diagnostics
    assert "auth_can_i_get_deployments_by_namespace" in diagnostics


def _assert_verify_blocker_present(data: dict) -> None:
    assert "verify_blocker" in data


def _load_explain_events(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_k8s_verify_no_kubectl_still_writes_report_ok_false(mk_path: Path, tmp_path: Path) -> None:
    out_dir = tmp_path / "out"
    plan = tmp_path / "plan.json"
    plan.write_text(
        json.dumps([{"namespace": "ns1", "name": "dep1", "patch": {"spec": {"replicas": 1}}}]),
        encoding="utf-8",
    )

    fake = tmp_path / "nope" / "kubectl"
    cp = _run(mk_path, ["k8s", "verify", "--plan", str(plan), "--out", str(out_dir)], env={"KUBECTL": str(fake)})
    assert cp.returncode == 0

    latest = out_dir / "k8s_verify_latest.json"
    assert latest.exists()
    data = json.loads(latest.read_text(encoding="utf-8"))
    assert data["ok"] is False
    assert data["checks"]["kubectl_present"] is False
    _assert_verify_blocker_present(data)
    assert data["verify_blocker"]["kind"] == "kubectl_missing"
    assert data["verify_blocker"]["index"] is None
    _assert_diagnostics_keys(data)


def test_k8s_verify_with_fake_kubectl_ok_true(mk_path: Path, tmp_path: Path) -> None:
    out_dir = tmp_path / "out"
    plan = tmp_path / "plan.json"
    plan.write_text(
        json.dumps([{"namespace": "ns1", "name": "dep1", "patch": {"spec": {"replicas": 1}}}]),
        encoding="utf-8",
    )

    kubectl = tmp_path / "kubectl"
    kubectl.write_text(
        """#!/usr/bin/env bash
set -Eeuo pipefail

if [[ $# -ge 2 && "$1" == "config" && "$2" == "current-context" ]]; then
  echo "test-context"
  exit 0
fi

if [[ $# -ge 4 && "$1" == "get" && "$2" == "namespace/ns1" && "$3" == "-o" && "$4" == "name" ]]; then
  echo "namespace/ns1"
  exit 0
fi

if [[ $# -ge 6 && "$1" == "-n" && "$2" == "ns1" && "$3" == "get" && "$4" == "deployment/dep1" && "$5" == "-o" && "$6" == "name" ]]; then
  echo "deployment.apps/dep1"
  exit 0
fi

if [[ $# -ge 5 && "$1" == "-n" && "$2" == "ns1" && "$3" == "patch" && "$4" == "deployment/dep1" ]]; then
  echo '{"kind":"Deployment","metadata":{"name":"dep1"}}'
  exit 0
fi

if [[ $# -ge 6 && "$1" == "-n" && "$2" == "ns1" && "$3" == "auth" && "$4" == "can-i" && "$5" == "patch" && "$6" == "deployments" ]]; then
  echo "yes"
  exit 0
fi

if [[ $# -ge 6 && "$1" == "-n" && "$2" == "ns1" && "$3" == "auth" && "$4" == "can-i" && "$5" == "get" && "$6" == "deployments" ]]; then
  echo "yes"
  exit 0
fi

echo "unexpected args: $*" >&2
exit 1
""",
        encoding="utf-8",
    )
    kubectl.chmod(0o755)

    cp = _run(mk_path, ["k8s", "verify", "--plan", str(plan), "--out", str(out_dir)], env={"KUBECTL": str(kubectl)})
    assert cp.returncode == 0

    latest = out_dir / "k8s_verify_latest.json"
    assert latest.exists()
    data = json.loads(latest.read_text(encoding="utf-8"))

    assert data["kubectl_context"] == "test-context"
    assert data["ok"] is True
    assert data["checks"]["kubectl_present"] is True
    assert len(data["checks"]["items"]) == 1
    assert data["checks"]["items"][0]["namespace_exists"] is True
    assert data["checks"]["items"][0]["deployment_exists"] is True
    assert data["checks"]["items"][0]["dry_run"]["ok"] is True
    assert data["diagnostics"]["auth_can_i_patch_deployments"] is True
    assert data["diagnostics"]["auth_can_i_get_deployments"] is True
    _assert_verify_blocker_present(data)
    assert data["verify_blocker"] is None
    _assert_diagnostics_keys(data)


def test_k8s_verify_namespace_missing_sets_blocker(mk_path: Path, tmp_path: Path) -> None:
    out_dir = tmp_path / "out"
    plan = tmp_path / "plan.json"
    plan.write_text(
        json.dumps(
            [
                {"namespace": "ns1", "name": "dep1", "patch": {"spec": {"replicas": 1}}},
                {"namespace": "ns2", "name": "dep2", "patch": {"spec": {"replicas": 2}}},
            ]
        ),
        encoding="utf-8",
    )

    kubectl = tmp_path / "kubectl"
    kubectl.write_text(
        """#!/usr/bin/env bash
set -Eeuo pipefail

if [[ $# -ge 2 && "$1" == "config" && "$2" == "current-context" ]]; then
  echo "test-context"
  exit 0
fi

if [[ $# -ge 4 && "$1" == "version" && "$2" == "--client" && "$3" == "-o" && "$4" == "json" ]]; then
  echo '{"clientVersion":{"gitVersion":"v1.29.0"}}'
  exit 0
fi

if [[ $# -ge 3 && "$1" == "version" && "$2" == "-o" && "$3" == "json" ]]; then
  echo '{"serverVersion":{"gitVersion":"v1.28.0"}}'
  exit 0
fi

if [[ $# -ge 4 && "$1" == "get" && "$2" == "namespace/ns1" && "$3" == "-o" && "$4" == "name" ]]; then
  echo "namespace/ns1 not found" >&2
  exit 1
fi

if [[ $# -ge 4 && "$1" == "get" && "$2" == "namespace/ns2" && "$3" == "-o" && "$4" == "name" ]]; then
  echo "namespace/ns2"
  exit 0
fi

if [[ $# -ge 6 && "$1" == "-n" && "$2" == "ns1" && "$3" == "get" && "$4" == "deployment/dep1" && "$5" == "-o" && "$6" == "name" ]]; then
  echo "deployment.apps/dep1 not found" >&2
  exit 1
fi

if [[ $# -ge 6 && "$1" == "-n" && "$2" == "ns2" && "$3" == "get" && "$4" == "deployment/dep2" && "$5" == "-o" && "$6" == "name" ]]; then
  echo "deployment.apps/dep2"
  exit 0
fi

if [[ $# -ge 5 && "$1" == "-n" && "$2" == "ns2" && "$3" == "patch" && "$4" == "deployment/dep2" ]]; then
  echo '{"kind":"Deployment","metadata":{"name":"dep2"}}'
  exit 0
fi

if [[ $# -ge 6 && "$1" == "-n" && "$2" == "ns2" && "$3" == "auth" && "$4" == "can-i" && "$5" == "patch" && "$6" == "deployments" ]]; then
  echo "yes"
  exit 0
fi

if [[ $# -ge 6 && "$1" == "-n" && "$2" == "ns2" && "$3" == "auth" && "$4" == "can-i" && "$5" == "get" && "$6" == "deployments" ]]; then
  echo "yes"
  exit 0
fi

echo "unexpected args: $*" >&2
exit 1
""",
        encoding="utf-8",
    )
    kubectl.chmod(0o755)

    cp = _run(mk_path, ["k8s", "verify", "--plan", str(plan), "--out", str(out_dir)], env={"KUBECTL": str(kubectl)})
    assert cp.returncode == 0

    latest = out_dir / "k8s_verify_latest.json"
    assert latest.exists()
    data = json.loads(latest.read_text(encoding="utf-8"))
    assert data["ok"] is False
    _assert_verify_blocker_present(data)
    assert data["verify_blocker"]["kind"] == "namespace_missing"
    assert data["verify_blocker"]["index"] == 0
    assert data["verify_blocker"]["namespace"] == "ns1"
    assert data["verify_blocker"]["name"] == "dep1"
    _assert_diagnostics_keys(data)


def test_k8s_verify_patch_forbidden_sets_rbac_denied_blocker(mk_path: Path, tmp_path: Path) -> None:
    out_dir = tmp_path / "out"
    plan = tmp_path / "plan.json"
    plan.write_text(
        json.dumps([{"namespace": "ns1", "name": "dep1", "patch": {"spec": {"replicas": 3}}}]),
        encoding="utf-8",
    )

    kubectl = tmp_path / "kubectl"
    kubectl.write_text(
        """#!/usr/bin/env bash
set -Eeuo pipefail

if [[ $# -ge 2 && "$1" == "config" && "$2" == "current-context" ]]; then
  echo "test-context"
  exit 0
fi

if [[ $# -ge 4 && "$1" == "version" && "$2" == "--client" && "$3" == "-o" && "$4" == "json" ]]; then
  echo '{"clientVersion":{"gitVersion":"v1.29.0"}}'
  exit 0
fi

if [[ $# -ge 3 && "$1" == "version" && "$2" == "-o" && "$3" == "json" ]]; then
  echo '{"serverVersion":{"gitVersion":"v1.28.0"}}'
  exit 0
fi

if [[ $# -ge 4 && "$1" == "get" && "$2" == "namespace/ns1" && "$3" == "-o" && "$4" == "name" ]]; then
  echo "namespace/ns1"
  exit 0
fi

if [[ $# -ge 6 && "$1" == "-n" && "$2" == "ns1" && "$3" == "get" && "$4" == "deployment/dep1" && "$5" == "-o" && "$6" == "name" ]]; then
  echo "deployment.apps/dep1"
  exit 0
fi

if [[ $# -ge 5 && "$1" == "-n" && "$2" == "ns1" && "$3" == "patch" && "$4" == "deployment/dep1" ]]; then
  echo 'Error from server (Forbidden): deployments.apps "dep1" is forbidden: User "system:serviceaccount:ns1:sa" cannot patch resource "deployments" in API group "apps" in the namespace "ns1"' >&2
  exit 1
fi

if [[ $# -ge 6 && "$1" == "-n" && "$2" == "ns1" && "$3" == "auth" && "$4" == "can-i" && "$5" == "patch" && "$6" == "deployments" ]]; then
  echo "no"
  exit 1
fi

if [[ $# -ge 6 && "$1" == "-n" && "$2" == "ns1" && "$3" == "auth" && "$4" == "can-i" && "$5" == "get" && "$6" == "deployments" ]]; then
  echo "yes"
  exit 0
fi

echo "unexpected args: $*" >&2
exit 1
""",
        encoding="utf-8",
    )
    kubectl.chmod(0o755)

    cp = _run(mk_path, ["k8s", "verify", "--plan", str(plan), "--out", str(out_dir)], env={"KUBECTL": str(kubectl)})
    assert cp.returncode == 0

    latest = out_dir / "k8s_verify_latest.json"
    data = json.loads(latest.read_text(encoding="utf-8"))
    assert data["ok"] is False
    assert data["checks"]["items"][0]["dry_run"]["mode"] == "server"
    assert data["verify_blocker"]["kind"] == "rbac_denied"
    rbac = data.get("details", {}).get("rbac")
    assert isinstance(rbac, dict)
    assert rbac["user"] == "system:serviceaccount:ns1:sa"
    assert rbac["verb"] == "patch"
    assert rbac["resource"] == "deployments"
    assert rbac["api_group"] == "apps"
    assert rbac["namespace"] == "ns1"
    assert rbac["scope"] == "namespaced"
    assert isinstance(rbac.get("hint"), str) and rbac["hint"]
    assert data["diagnostics"]["auth_can_i_patch_deployments"] is False
    assert data["diagnostics"]["auth_can_i_get_deployments"] is True


def test_k8s_verify_patch_not_found_sets_deployment_missing_blocker(mk_path: Path, tmp_path: Path) -> None:
    out_dir = tmp_path / "out"
    plan = tmp_path / "plan.json"
    plan.write_text(
        json.dumps([{"namespace": "ns1", "name": "dep1", "patch": {"spec": {"replicas": 3}}}]),
        encoding="utf-8",
    )

    kubectl = tmp_path / "kubectl"
    kubectl.write_text(
        """#!/usr/bin/env bash
set -Eeuo pipefail

if [[ $# -ge 2 && "$1" == "config" && "$2" == "current-context" ]]; then
  echo "test-context"
  exit 0
fi

if [[ $# -ge 4 && "$1" == "version" && "$2" == "--client" && "$3" == "-o" && "$4" == "json" ]]; then
  echo '{"clientVersion":{"gitVersion":"v1.29.0"}}'
  exit 0
fi

if [[ $# -ge 3 && "$1" == "version" && "$2" == "-o" && "$3" == "json" ]]; then
  echo '{"serverVersion":{"gitVersion":"v1.28.0"}}'
  exit 0
fi

if [[ $# -ge 4 && "$1" == "get" && "$2" == "namespace/ns1" && "$3" == "-o" && "$4" == "name" ]]; then
  echo "namespace/ns1"
  exit 0
fi

if [[ $# -ge 6 && "$1" == "-n" && "$2" == "ns1" && "$3" == "get" && "$4" == "deployment/dep1" && "$5" == "-o" && "$6" == "name" ]]; then
  echo "deployment.apps/dep1"
  exit 0
fi

if [[ $# -ge 5 && "$1" == "-n" && "$2" == "ns1" && "$3" == "patch" && "$4" == "deployment/dep1" ]]; then
  echo 'Error from server (NotFound): deployments.apps "dep1" not found' >&2
  exit 1
fi

if [[ $# -ge 6 && "$1" == "-n" && "$2" == "ns1" && "$3" == "auth" && "$4" == "can-i" && "$5" == "patch" && "$6" == "deployments" ]]; then
  echo "yes"
  exit 0
fi

if [[ $# -ge 6 && "$1" == "-n" && "$2" == "ns1" && "$3" == "auth" && "$4" == "can-i" && "$5" == "get" && "$6" == "deployments" ]]; then
  echo "yes"
  exit 0
fi

echo "unexpected args: $*" >&2
exit 1
""",
        encoding="utf-8",
    )
    kubectl.chmod(0o755)

    cp = _run(mk_path, ["k8s", "verify", "--plan", str(plan), "--out", str(out_dir)], env={"KUBECTL": str(kubectl)})
    assert cp.returncode == 0

    latest = out_dir / "k8s_verify_latest.json"
    data = json.loads(latest.read_text(encoding="utf-8"))
    assert data["ok"] is False
    assert data["checks"]["items"][0]["dry_run"]["mode"] == "server"
    assert data["verify_blocker"]["kind"] == "deployment_missing"


def test_k8s_verify_mixed_namespaces_collects_auth_can_i_per_namespace(
    mk_path: Path, tmp_path: Path
) -> None:
    out_dir = tmp_path / "out"
    plan = tmp_path / "plan.json"
    calls_path = tmp_path / "auth_calls.txt"
    plan.write_text(
        json.dumps(
            [
                {"namespace": "ns1", "name": "dep1", "patch": {"spec": {"replicas": 1}}},
                {"namespace": "ns2", "name": "dep1", "patch": {"spec": {"replicas": 2}}},
            ]
        ),
        encoding="utf-8",
    )

    kubectl = tmp_path / "kubectl"
    kubectl.write_text(
        """#!/usr/bin/env bash
set -Eeuo pipefail

if [[ "$*" == *" auth can-i "* ]]; then
  echo "$*" >> "${CALLS_PATH}"
  if [[ "$*" == *"-n ns1"* && "$*" == *" can-i patch deployments"* ]]; then
    echo "yes"
    exit 0
  fi
  if [[ "$*" == *"-n ns1"* && "$*" == *" can-i get deployments"* ]]; then
    echo "yes"
    exit 0
  fi
  if [[ "$*" == *"-n ns2"* && "$*" == *" can-i patch deployments"* ]]; then
    echo "maybe"
    exit 0
  fi
  if [[ "$*" == *"-n ns2"* && "$*" == *" can-i get deployments"* ]]; then
    echo "yes"
    exit 0
  fi
  echo "unexpected auth args: $*" >&2
  exit 1
fi

if [[ $# -ge 2 && "$1" == "config" && "$2" == "current-context" ]]; then
  echo "test-context"
  exit 0
fi

if [[ $# -ge 4 && "$1" == "version" && "$2" == "--client" && "$3" == "-o" && "$4" == "json" ]]; then
  echo '{"clientVersion":{"gitVersion":"v1.29.0"}}'
  exit 0
fi

if [[ $# -ge 3 && "$1" == "version" && "$2" == "-o" && "$3" == "json" ]]; then
  echo '{"serverVersion":{"gitVersion":"v1.28.0"}}'
  exit 0
fi

if [[ $# -ge 4 && "$1" == "get" && "$2" == "namespace/ns1" && "$3" == "-o" && "$4" == "name" ]]; then
  echo "namespace/ns1"
  exit 0
fi

if [[ $# -ge 4 && "$1" == "get" && "$2" == "namespace/ns2" && "$3" == "-o" && "$4" == "name" ]]; then
  echo "namespace/ns2"
  exit 0
fi

if [[ $# -ge 6 && "$1" == "-n" && "$2" == "ns1" && "$3" == "get" && "$4" == "deployment/dep1" && "$5" == "-o" && "$6" == "name" ]]; then
  echo "deployment.apps/dep1"
  exit 0
fi

if [[ $# -ge 6 && "$1" == "-n" && "$2" == "ns2" && "$3" == "get" && "$4" == "deployment/dep1" && "$5" == "-o" && "$6" == "name" ]]; then
  echo "deployment.apps/dep1"
  exit 0
fi

if [[ $# -ge 5 && "$1" == "-n" && "$2" == "ns1" && "$3" == "patch" && "$4" == "deployment/dep1" ]]; then
  echo '{"kind":"Deployment","metadata":{"name":"dep1"}}'
  exit 0
fi

if [[ $# -ge 5 && "$1" == "-n" && "$2" == "ns2" && "$3" == "patch" && "$4" == "deployment/dep1" ]]; then
  echo '{"kind":"Deployment","metadata":{"name":"dep1"}}'
  exit 0
fi

echo "unexpected args: $*" >&2
exit 1
""",
        encoding="utf-8",
    )
    kubectl.chmod(0o755)

    cp = _run(
        mk_path,
        ["k8s", "verify", "--plan", str(plan), "--out", str(out_dir)],
        env={"KUBECTL": str(kubectl), "CALLS_PATH": str(calls_path)},
    )
    assert cp.returncode == 0

    latest = out_dir / "k8s_verify_latest.json"
    assert latest.exists()
    data = json.loads(latest.read_text(encoding="utf-8"))
    _assert_diagnostics_keys(data)
    assert data["diagnostics"]["auth_can_i_patch_deployments"] is None
    assert data["diagnostics"]["auth_can_i_get_deployments"] is None
    assert data["diagnostics"]["auth_can_i_patch_deployments_by_namespace"] == {
        "ns1": True,
        "ns2": None,
    }
    assert data["diagnostics"]["auth_can_i_get_deployments_by_namespace"] == {
        "ns1": True,
        "ns2": True,
    }
    assert data["checks"]["items"][0]["auth_can_i_patch_deployments"] is True
    assert data["checks"]["items"][0]["auth_can_i_get_deployments"] is True
    assert data["checks"]["items"][1]["auth_can_i_patch_deployments"] is None
    assert data["checks"]["items"][1]["auth_can_i_get_deployments"] is True

    calls = calls_path.read_text(encoding="utf-8").splitlines()
    assert any("-n ns1 auth can-i patch deployments" in line for line in calls)
    assert any("-n ns1 auth can-i get deployments" in line for line in calls)
    assert any("-n ns2 auth can-i patch deployments" in line for line in calls)
    assert any("-n ns2 auth can-i get deployments" in line for line in calls)

    explain_events = _load_explain_events(out_dir / "explain.jsonl")
    assert any(
        ev.get("event") == "k8s_verify_diagnostic"
        and ev.get("payload", {}).get("name") == "auth_can_i_patch_deployments"
        and ev.get("payload", {}).get("namespace") == "ns2"
        for ev in explain_events
    )
