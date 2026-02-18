import hashlib
import json
import os
import subprocess
from pathlib import Path


def _run(mk: Path, args: list[str], env: dict | None = None) -> subprocess.CompletedProcess[str]:
    process_env = os.environ.copy()
    if env:
        process_env.update(env)
    return subprocess.run([str(mk), *args], text=True, capture_output=True, env=process_env)


def test_mk078_fleet_policy_propagation_with_path_stub(tmp_path: Path, mk_path: Path) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    kubectl = bin_dir / "kubectl"
    kubectl.write_text(
        """#!/usr/bin/env bash
set -Eeuo pipefail

if [[ $# -eq 2 && "$1" == "config" && "$2" == "current-context" ]]; then
  echo "ctx-a"
  exit 0
fi

if [[ $# -eq 7 && "$1" == "--context" && "$2" == "ctx-a" && "$3" == "get" && "$4" == "deployments" && "$5" == "-A" && "$6" == "-o" && "$7" == "json" ]]; then
  echo '{"items":[{"metadata":{"namespace":"z-ns","name":"z-app"}},{"metadata":{"namespace":"default","name":"trainer","annotations":{"modekeeper/policy.ref":"safe","modekeeper/policy.version":"old"}}}]}'
  exit 0
fi

echo "unexpected args: $*" >&2
exit 1
""",
        encoding="utf-8",
    )
    kubectl.chmod(0o755)

    policy_file = tmp_path / "policy.json"
    policy_file.write_text('{"mode":"safe","limit":2}\n', encoding="utf-8")

    out_dir = tmp_path / "out"
    env = {"PATH": f"{bin_dir}:{os.environ.get('PATH', '')}"}
    cp = _run(
        mk_path,
        ["fleet", "policy", "--policy", str(policy_file), "--out", str(out_dir)],
        env=env,
    )
    assert cp.returncode == 0

    latest = out_dir / "policy_propagation_latest.json"
    assert latest.exists()
    data = json.loads(latest.read_text(encoding="utf-8"))

    expected_sha = hashlib.sha256(policy_file.read_bytes()).hexdigest()
    assert data.get("schema") == "policy_propagation.v0"
    assert data.get("desired_policy", {}).get("policy_ref") == str(policy_file)
    assert data.get("desired_policy", {}).get("sha256") == expected_sha
    assert data.get("desired_policy", {}).get("version_short") == expected_sha[:12]

    deployments = data.get("contexts", [])[0].get("deployments", [])
    assert deployments == [
        {
            "namespace": "default",
            "name": "trainer",
            "current_policy_ref": "safe",
            "current_policy_version": "old",
            "desired_policy_ref": str(policy_file),
            "desired_policy_version": expected_sha[:12],
            "change_required": True,
            "rollback_policy_ref": "safe",
            "rollback_policy_version": "old",
        },
        {
            "namespace": "z-ns",
            "name": "z-app",
            "current_policy_ref": None,
            "current_policy_version": None,
            "desired_policy_ref": str(policy_file),
            "desired_policy_version": expected_sha[:12],
            "change_required": True,
            "rollback_policy_ref": None,
            "rollback_policy_version": None,
        },
    ]
