import json
import os
import subprocess
from pathlib import Path


def _run(mk: Path, args: list[str], env: dict | None = None) -> subprocess.CompletedProcess[str]:
    merged = os.environ.copy()
    if env:
        merged.update(env)
    return subprocess.run([str(mk), *args], text=True, capture_output=True, env=merged)


def _write_fake_kubectl(path: Path) -> None:
    path.write_text(
        """#!/usr/bin/env bash
set -Eeuo pipefail

if [[ $# -ge 2 && "$1" == "config" && "$2" == "current-context" ]]; then
  echo "fake-context"
  exit 0
fi

if [[ $# -ge 4 && "$1" == "version" && "$2" == "--client" && "$3" == "-o" && "$4" == "json" ]]; then
  echo '{"clientVersion":{"gitVersion":"v1.30.0"}}'
  exit 0
fi

if [[ $# -ge 3 && "$1" == "version" && "$2" == "-o" && "$3" == "json" ]]; then
  echo '{"serverVersion":{"gitVersion":"v1.29.0"}}'
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

if [[ $# -ge 6 && "$1" == "-n" && "$2" == "ns2" && "$3" == "get" && "$4" == "deployment/dep2" && "$5" == "-o" && "$6" == "name" ]]; then
  echo "deployment.apps/dep2"
  exit 0
fi

if [[ $# -ge 5 && "$1" == "-n" && "$3" == "auth" && "$4" == "can-i" ]]; then
  echo "yes"
  exit 0
fi

if [[ $# -ge 5 && "$1" == "-n" && "$3" == "patch" ]]; then
  if [[ "$*" == *"--dry-run=server"* ]]; then
    echo '{"kind":"Deployment","metadata":{"name":"dry-run"}}'
    exit 0
  fi

  if [[ -n "${PATCH_COUNTER_PATH:-}" ]]; then
    count=0
    if [[ -f "${PATCH_COUNTER_PATH}" ]]; then
      count="$(cat "${PATCH_COUNTER_PATH}")"
    fi
    count=$((count + 1))
    echo "${count}" > "${PATCH_COUNTER_PATH}"

    fail_on="${FAIL_PATCH_CALL:-0}"
    if [[ "${fail_on}" != "0" && "${count}" -eq "${fail_on}" ]]; then
      echo "forced apply failure on call ${count}" >&2
      exit 7
    fi
  fi

  echo "patched"
  exit 0
fi

echo "unexpected args: $*" >&2
exit 1
""",
        encoding="utf-8",
    )
    path.chmod(0o755)


def _assert_item_object_fields(items: list[dict]) -> None:
    for item in items:
        obj = item.get("object")
        assert isinstance(obj, dict)
        assert isinstance(obj.get("namespace"), str) and obj["namespace"]
        assert isinstance(obj.get("name"), str) and obj["name"]
        assert obj.get("kind") == "Deployment"


def _write_verify_ok(plan_dir: Path) -> None:
    (plan_dir / "k8s_verify_latest.json").write_text(json.dumps({"ok": True}), encoding="utf-8")


def test_k8s_verify_accepts_multi_object_envelope_and_reports_objects(mk_path: Path, tmp_path: Path) -> None:
    plan_path = tmp_path / "plan_multi.json"
    plan_path.write_text(
        json.dumps(
            {
                "schema_version": "k8s_plan.v1",
                "items": [
                    {"namespace": "ns1", "name": "dep1", "patch": {"spec": {"replicas": 1}}},
                    {"namespace": "ns2", "name": "dep2", "patch": {"spec": {"replicas": 2}}},
                ],
            }
        ),
        encoding="utf-8",
    )

    kubectl = tmp_path / "kubectl"
    _write_fake_kubectl(kubectl)
    out_dir = tmp_path / "verify_out"

    cp = _run(mk_path, ["k8s", "verify", "--plan", str(plan_path), "--out", str(out_dir)], env={"KUBECTL": str(kubectl)})
    assert cp.returncode == 0

    report = json.loads((out_dir / "k8s_verify_latest.json").read_text(encoding="utf-8"))
    objects = report.get("objects")
    assert isinstance(objects, list)
    assert len(objects) == 2
    assert [obj.get("kind") for obj in objects] == ["Deployment", "Deployment"]

    checks_items = report.get("checks", {}).get("items")
    assert isinstance(checks_items, list)
    assert len(checks_items) == 2
    _assert_item_object_fields(checks_items)

    top_items = report.get("items")
    if isinstance(top_items, list):
        assert len(top_items) == 2
        _assert_item_object_fields(top_items)


def test_k8s_apply_multi_object_reports_objects_and_items_with_fail_fast(mk_path: Path, tmp_path: Path) -> None:
    plan_path = tmp_path / "plan_multi_apply.json"
    plan_path.write_text(
        json.dumps(
            {
                "schema_version": "k8s_plan.v1",
                "items": [
                    {"namespace": "ns1", "name": "dep1", "patch": {"spec": {"replicas": 2}}},
                    {"namespace": "ns2", "name": "dep2", "patch": {"spec": {"replicas": 3}}},
                ],
            }
        ),
        encoding="utf-8",
    )
    out_dir = tmp_path / "apply_out"

    cp = _run(
        mk_path,
        ["k8s", "apply", "--plan", str(plan_path), "--out", str(out_dir)],
        env={"MODEKEEPER_PAID": "1", "MODEKEEPER_INTERNAL_OVERRIDE": "1"},
    )
    assert cp.returncode == 2
    assert cp.stderr.strip() == "PRO REQUIRED: k8s apply"

    report = json.loads((out_dir / "k8s_apply_latest.json").read_text(encoding="utf-8"))
    assert report.get("block_reason") == "pro_required"
    assert report.get("reason") == "pro_required"
    objects = report.get("objects")
    assert isinstance(objects, list)
    assert len(objects) == 2

    items = report.get("items")
    assert isinstance(items, list)
    assert len(items) == 2
    _assert_item_object_fields(items)


def test_k8s_verify_accepts_legacy_single_object_shape(mk_path: Path, tmp_path: Path) -> None:
    plan_path = tmp_path / "plan_single_legacy.json"
    plan_path.write_text(
        json.dumps({"namespace": "ns1", "name": "dep1", "patch": {"spec": {"replicas": 1}}}),
        encoding="utf-8",
    )

    kubectl = tmp_path / "kubectl"
    _write_fake_kubectl(kubectl)
    out_dir = tmp_path / "verify_single_out"

    cp = _run(mk_path, ["k8s", "verify", "--plan", str(plan_path), "--out", str(out_dir)], env={"KUBECTL": str(kubectl)})
    assert cp.returncode == 0

    report = json.loads((out_dir / "k8s_verify_latest.json").read_text(encoding="utf-8"))
    assert report.get("k8s_namespace") == "ns1"
    assert report.get("k8s_deployment") == "dep1"
    assert isinstance(report.get("checks", {}).get("items"), list)
    assert len(report["checks"]["items"]) == 1
    _assert_item_object_fields(report["checks"]["items"])
