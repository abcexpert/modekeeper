import json
import os
import subprocess
from pathlib import Path


def _write_fake_kubectl(path: Path, log_path: Path) -> None:
    script = f"""#!/usr/bin/env bash
set -Eeuo pipefail

echo "$*" >> "{log_path}"

echo "unexpected args: $*" >&2
exit 1
"""
    path.write_text(script, encoding="utf-8")
    path.chmod(0o755)


def test_closed_loop_report_artifacts_apply_paths_are_pro_gated(tmp_path: Path, mk_path: Path) -> None:
    out_dir = tmp_path / "closed_loop_out"
    kubectl_log = tmp_path / "kubectl.log"
    kubectl = tmp_path / "kubectl"
    _write_fake_kubectl(kubectl, kubectl_log)
    env = {
        **os.environ,
        "MODEKEEPER_KILL_SWITCH": "1",
        "MODEKEEPER_PAID": "1",
        "MODEKEEPER_INTERNAL_OVERRIDE": "1",
        "KUBECTL": str(kubectl),
    }
    cp = subprocess.run(
        [
            str(mk_path),
            "closed-loop",
            "run",
            "--apply",
            "--k8s-namespace",
            "ns1",
            "--k8s-deployment",
            "dep1",
            "--out",
            str(out_dir),
        ],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )
    assert cp.returncode == 2
    assert cp.stderr.strip() == "PRO REQUIRED: closed-loop --apply"

    latest = json.loads((out_dir / "closed_loop_latest.json").read_text(encoding="utf-8"))
    assert latest.get("apply_requested") is True
    assert latest.get("apply_blocked_reason") == "pro_required"
    apply_latest = json.loads((out_dir / "k8s_apply_latest.json").read_text(encoding="utf-8"))
    assert apply_latest.get("block_reason") == "pro_required"

    if kubectl_log.exists():
        assert "--patch" not in kubectl_log.read_text(encoding="utf-8")


def test_closed_loop_writes_k8s_plan(tmp_path: Path, mk_path: Path) -> None:
    out_dir = tmp_path / "closed_loop_out"
    subprocess.run(
        [
            str(mk_path),
            "closed-loop",
            "run",
            "--scenario",
            "drift",
            "--k8s-namespace",
            "ns1",
            "--k8s-deployment",
            "dep1",
            "--out",
            str(out_dir),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    plan_path = out_dir / "k8s_plan.json"
    assert plan_path.exists()
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    assert isinstance(plan, list)
    assert len(plan) >= 1
