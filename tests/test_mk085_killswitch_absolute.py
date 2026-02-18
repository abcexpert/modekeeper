import json
import os
import subprocess
from pathlib import Path


def _write_plan(path: Path) -> None:
    path.write_text(
        json.dumps([{"namespace": "ns1", "name": "dep1", "patch": {"spec": {"replicas": 2}}}]),
        encoding="utf-8",
    )


def _run(mk: Path, args: list[str], env: dict) -> subprocess.CompletedProcess[str]:
    return subprocess.run([str(mk), *args], text=True, capture_output=True, env=env)


def test_k8s_apply_pro_required_even_with_kill_switch_and_override(tmp_path: Path, mk_path: Path) -> None:
    plan = tmp_path / "plan.json"
    _write_plan(plan)
    out_dir = tmp_path / "out"

    env = {
        **os.environ,
        "MODEKEEPER_KILL_SWITCH": "1",
        "MODEKEEPER_PAID": "1",
        "MODEKEEPER_INTERNAL_OVERRIDE": "1",
    }
    cp = _run(mk_path, ["k8s", "apply", "--plan", str(plan), "--out", str(out_dir)], env)
    assert cp.returncode == 2
    assert cp.stderr.strip() == "PRO REQUIRED: k8s apply"
    report = json.loads((out_dir / "k8s_apply_latest.json").read_text(encoding="utf-8"))
    assert report.get("block_reason") == "pro_required"


def test_closed_loop_apply_pro_required_even_with_kill_switch(tmp_path: Path, mk_path: Path) -> None:
    out_dir = tmp_path / "out"

    env = {
        **os.environ,
        "MODEKEEPER_KILL_SWITCH": "1",
        "MODEKEEPER_PAID": "1",
        "MODEKEEPER_INTERNAL_OVERRIDE": "1",
    }
    cp = _run(
        mk_path,
        [
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
        env,
    )
    assert cp.returncode == 2
    assert cp.stderr.strip() == "PRO REQUIRED: closed-loop --apply"

    latest = json.loads((out_dir / "closed_loop_latest.json").read_text(encoding="utf-8"))
    assert latest.get("apply_blocked_reason") == "pro_required"


def test_closed_loop_watch_apply_pro_required_at_entrypoint(tmp_path: Path, mk_path: Path) -> None:
    out_dir = tmp_path / "watch_out"
    observe_path = tmp_path / "observe.jsonl"
    observe_path.write_text(
        "\n".join(
            [
                '{"ts":"2026-01-01T00:00:00Z","step_time_ms":100,"loss":1.0}',
                '{"ts":"2026-01-01T00:00:01Z","step_time_ms":100,"loss":1.0}',
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    env = {
        **os.environ,
        "MODEKEEPER_KILL_SWITCH": "1",
        "MODEKEEPER_PAID": "1",
        "MODEKEEPER_INTERNAL_OVERRIDE": "1",
    }
    cp = _run(
        mk_path,
        [
            "closed-loop",
            "watch",
            "--scenario",
            "drift",
            "--apply",
            "--observe-source",
            "file",
            "--observe-path",
            str(observe_path),
            "--out",
            str(out_dir),
            "--max-iterations",
            "1",
            "--interval",
            "0s",
        ],
        env,
    )
    assert cp.returncode == 2
    assert cp.stderr.strip() == "PRO REQUIRED: closed-loop watch --apply"
    assert not (out_dir / "iter_0001").exists()
