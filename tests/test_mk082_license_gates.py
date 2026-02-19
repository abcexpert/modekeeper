import json
import subprocess
from pathlib import Path


def _run(mk: Path, args: list[str], env: dict | None = None) -> subprocess.CompletedProcess[str]:
    merged_env = None
    if env is not None:
        import os

        merged_env = os.environ.copy()
        merged_env.update(env)
    return subprocess.run([str(mk), *args], text=True, capture_output=True, env=merged_env)


def _write_plan(path: Path) -> None:
    path.write_text(
        json.dumps([{"namespace": "ns1", "name": "dep1", "patch": {"spec": {"replicas": 2}}}]) + "\n",
        encoding="utf-8",
    )


def _assert_pro_required(out_dir: Path, stderr: str) -> None:
    assert stderr.strip() == "PRO REQUIRED: k8s apply"
    report = json.loads((out_dir / "k8s_apply_latest.json").read_text(encoding="utf-8"))
    assert report.get("block_reason") == "pro_required"
    assert report.get("reason") == "pro_required"


def _assert_kill_switch_blocked(out_dir: Path, stderr: str) -> None:
    assert stderr.strip() == "ERROR: MODEKEEPER_KILL_SWITCH=1 blocks apply/mutate operations"
    report = json.loads((out_dir / "k8s_apply_latest.json").read_text(encoding="utf-8"))
    assert report.get("block_reason") == "kill_switch_active"
    assert report.get("reason") == "kill_switch_active"


def test_apply_gate_is_pro_required_without_pro_install(tmp_path: Path, mk_path: Path) -> None:
    plan = tmp_path / "plan.json"
    _write_plan(plan)
    out_dir = tmp_path / "out"

    cp = _run(mk_path, ["k8s", "apply", "--plan", str(plan), "--out", str(out_dir)])
    assert cp.returncode == 2
    _assert_pro_required(out_dir, cp.stderr)


def test_apply_gate_kill_switch_has_absolute_precedence(tmp_path: Path, mk_path: Path) -> None:
    plan = tmp_path / "plan.json"
    _write_plan(plan)
    out_dir = tmp_path / "out"

    cp = _run(
        mk_path,
        ["k8s", "apply", "--plan", str(plan), "--out", str(out_dir)],
        env={
            "MODEKEEPER_PAID": "1",
            "MODEKEEPER_INTERNAL_OVERRIDE": "1",
            "MODEKEEPER_LICENSE_PATH": str(tmp_path / "dummy.license.json"),
            "MODEKEEPER_KILL_SWITCH": "1",
        },
    )
    assert cp.returncode == 2
    _assert_kill_switch_blocked(out_dir, cp.stderr)
