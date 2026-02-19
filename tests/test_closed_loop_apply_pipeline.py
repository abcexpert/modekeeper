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


def _write_observe_jsonl(path: Path) -> None:
    rows = [
        '{"ts":"2026-01-01T00:00:00Z","step_time_ms":100,"loss":1.0}',
        '{"ts":"2026-01-01T00:00:01Z","step_time_ms":100,"loss":1.0}',
        '{"ts":"2026-01-01T00:00:02Z","step_time_ms":100,"loss":1.0}',
        '{"ts":"2026-01-01T00:00:03Z","step_time_ms":100,"loss":1.0}',
    ]
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def test_closed_loop_run_dry_run_unaffected_by_verify_gate(tmp_path: Path, mk_path: Path) -> None:
    out_dir = tmp_path / "closed_loop_out"
    cp = subprocess.run(
        [
            str(mk_path),
            "closed-loop",
            "run",
            "--dry-run",
            "--out",
            str(out_dir),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert cp.returncode == 0

    latest = json.loads((out_dir / "closed_loop_latest.json").read_text(encoding="utf-8"))
    assert latest.get("apply_requested") is False
    assert latest.get("dry_run") is True


def test_closed_loop_apply_requires_pro_and_writes_reason_artifacts(tmp_path: Path, mk_path: Path) -> None:
    out_dir = tmp_path / "closed_loop_out"
    kubectl_log = tmp_path / "kubectl.log"
    kubectl = tmp_path / "kubectl"
    _write_fake_kubectl(kubectl, kubectl_log)

    env = {
        **os.environ,
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
    assert latest.get("apply_attempted") is False
    assert latest.get("apply_ok") is None
    assert latest.get("apply_blocked_reason") == "pro_required"
    assert latest.get("apply_decision_summary") == "apply blocked: pro_required"
    apply_latest = json.loads((out_dir / "k8s_apply_latest.json").read_text(encoding="utf-8"))
    assert apply_latest.get("block_reason") == "pro_required"
    assert apply_latest.get("reason") == "pro_required"

    if kubectl_log.exists():
        assert "--patch" not in kubectl_log.read_text(encoding="utf-8")


def test_closed_loop_apply_no_proposals_is_still_pro_required(tmp_path: Path, mk_path: Path) -> None:
    out_dir = tmp_path / "closed_loop_out"
    observe_path = tmp_path / "observe.jsonl"
    _write_observe_jsonl(observe_path)

    cp = subprocess.run(
        [
            str(mk_path),
            "closed-loop",
            "run",
            "--apply",
            "--observe-source",
            "file",
            "--observe-path",
            str(observe_path),
            "--out",
            str(out_dir),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert cp.returncode == 2
    assert cp.stderr.strip() == "PRO REQUIRED: closed-loop --apply"
    latest = json.loads((out_dir / "closed_loop_latest.json").read_text(encoding="utf-8"))
    assert latest.get("apply_blocked_reason") == "pro_required"
