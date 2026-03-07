import json
import os
import shutil
import subprocess
from pathlib import Path


def _run(mk: Path, args: list[str], env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    return subprocess.run([str(mk), *args], text=True, capture_output=True, check=False, env=merged_env)


def _write_fake_kubectl_verify_ok(path: Path, *, namespace: str, deployment: str) -> None:
    script = f"""#!/usr/bin/env bash
set -Eeuo pipefail

if [[ $# -ge 2 && "$1" == "config" && "$2" == "current-context" ]]; then
  echo "test-context"
  exit 0
fi

if [[ $# -ge 4 && "$1" == "version" && "$2" == "--client" && "$3" == "-o" && "$4" == "json" ]]; then
  echo '{{"clientVersion":{{"gitVersion":"v1.29.0"}}}}'
  exit 0
fi

if [[ $# -ge 3 && "$1" == "version" && "$2" == "-o" && "$3" == "json" ]]; then
  echo '{{"serverVersion":{{"gitVersion":"v1.28.0"}}}}'
  exit 0
fi

if [[ $# -ge 4 && "$1" == "get" && "$2" == "namespace/{namespace}" && "$3" == "-o" && "$4" == "name" ]]; then
  echo "namespace/{namespace}"
  exit 0
fi

if [[ $# -ge 6 && "$1" == "-n" && "$2" == "{namespace}" && "$3" == "get" && "$4" == "deployment/{deployment}" && "$5" == "-o" && "$6" == "name" ]]; then
  echo "deployment.apps/{deployment}"
  exit 0
fi

if [[ $# -ge 5 && "$1" == "-n" && "$2" == "{namespace}" && "$3" == "patch" && "$4" == "deployment/{deployment}" ]]; then
  echo '{{"kind":"Deployment","metadata":{{"name":"{deployment}"}}}}'
  exit 0
fi

if [[ $# -ge 6 && "$1" == "-n" && "$2" == "{namespace}" && "$3" == "auth" && "$4" == "can-i" && "$5" == "patch" && "$6" == "deployments" ]]; then
  echo "yes"
  exit 0
fi

if [[ $# -ge 6 && "$1" == "-n" && "$2" == "{namespace}" && "$3" == "auth" && "$4" == "can-i" && "$5" == "get" && "$6" == "deployments" ]]; then
  echo "yes"
  exit 0
fi

echo "unexpected args: $*" >&2
exit 1
"""
    path.write_text(script, encoding="utf-8")
    path.chmod(0o755)


def test_public_happy_path_contract_observe_plan_verify_export_handoff_pack(
    tmp_path: Path, mk_path: Path
) -> None:
    observe_fixture = Path("tests/data/observe/stable.jsonl")
    assert observe_fixture.exists()

    observe_out = tmp_path / "observe"
    plan_out = tmp_path / "plan"
    verify_out = tmp_path / "verify"
    handoff_in = tmp_path / "handoff_in"
    handoff_out = tmp_path / "handoff_out"

    observe_cp = _run(
        mk_path,
        [
            "observe",
            "--duration",
            "1s",
            "--source",
            "file",
            "--path",
            str(observe_fixture),
            "--out",
            str(observe_out),
        ],
    )
    assert observe_cp.returncode == 0, observe_cp.stderr
    observe_latest = json.loads((observe_out / "observe_latest.json").read_text(encoding="utf-8"))
    assert observe_latest.get("sample_count") == 4

    plan_cp = _run(
        mk_path,
        [
            "closed-loop",
            "run",
            "--scenario",
            "drift",
            "--dry-run",
            "--observe-source",
            "file",
            "--observe-path",
            str(observe_fixture),
            "--out",
            str(plan_out),
        ],
    )
    assert plan_cp.returncode == 0, plan_cp.stderr
    plan_latest = plan_out / "closed_loop_latest.json"
    plan_path = plan_out / "k8s_plan.json"
    assert plan_latest.exists()
    assert plan_path.exists()

    kubectl = tmp_path / "kubectl"
    _write_fake_kubectl_verify_ok(kubectl, namespace="ns1", deployment="dep1")
    verify_cp = _run(
        mk_path,
        ["k8s", "verify", "--plan", str(plan_path), "--out", str(verify_out)],
        env={"KUBECTL": str(kubectl)},
    )
    assert verify_cp.returncode == 0, verify_cp.stderr
    verify_latest_path = verify_out / "k8s_verify_latest.json"
    verify_latest = json.loads(verify_latest_path.read_text(encoding="utf-8"))
    assert verify_latest.get("ok") is True

    (handoff_in / "observe").mkdir(parents=True)
    (handoff_in / "plan").mkdir(parents=True)
    (handoff_in / "verify").mkdir(parents=True)
    shutil.copy2(observe_out / "observe_latest.json", handoff_in / "observe" / "observe_latest.json")
    shutil.copy2(plan_latest, handoff_in / "plan" / "closed_loop_latest.json")
    shutil.copy2(verify_latest_path, handoff_in / "verify" / "k8s_verify_latest.json")

    export_cp = _run(
        mk_path,
        ["export", "handoff-pack", "--in", str(handoff_in), "--out", str(handoff_out)],
    )
    assert export_cp.returncode == 0, export_cp.stderr

    manifest = json.loads((handoff_out / "handoff_manifest.json").read_text(encoding="utf-8"))
    files = manifest.get("files")
    rel_paths = {item.get("rel_path") for item in files} if isinstance(files, list) else set()
    assert "plan/closed_loop_latest.json" in rel_paths
    assert "verify/k8s_verify_latest.json" in rel_paths

    verify_script_cp = subprocess.run(
        ["bash", "HANDOFF_VERIFY.sh"],
        cwd=handoff_out,
        text=True,
        capture_output=True,
        check=False,
    )
    assert verify_script_cp.returncode == 0, verify_script_cp.stderr
    assert "OK" in verify_script_cp.stdout
