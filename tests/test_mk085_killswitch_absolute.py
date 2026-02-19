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


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_k8s_apply_kill_switch_blocks_even_with_override(tmp_path: Path, mk_path: Path) -> None:
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
    assert cp.stderr.strip() == "ERROR: MODEKEEPER_KILL_SWITCH=1 blocks apply/mutate operations"
    report = json.loads((out_dir / "k8s_apply_latest.json").read_text(encoding="utf-8"))
    assert report.get("block_reason") == "kill_switch_active"
    assert report.get("reason") == "kill_switch_active"
    assert report.get("kill_switch_signal") == "env:MODEKEEPER_KILL_SWITCH"


def test_closed_loop_apply_kill_switch_blocks_even_with_override(tmp_path: Path, mk_path: Path) -> None:
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
    assert cp.stderr.strip() == "ERROR: MODEKEEPER_KILL_SWITCH=1 blocks apply/mutate operations"

    latest = json.loads((out_dir / "closed_loop_latest.json").read_text(encoding="utf-8"))
    assert latest.get("apply_blocked_reason") == "kill_switch_active"
    assert latest.get("kill_switch_active") is True
    assert latest.get("kill_switch_signal") == "env:MODEKEEPER_KILL_SWITCH"
    trace = _read_jsonl(out_dir / "decision_trace_latest.jsonl")
    assert trace
    last_trace = trace[-1]
    results = last_trace.get("results") or {}
    assert results.get("kill_switch_active") is True
    assert results.get("blocked_reason") == "kill_switch_active"
    assert results.get("kill_switch_signal") == "env:MODEKEEPER_KILL_SWITCH"
    explain = _read_jsonl(out_dir / "explain.jsonl")
    apply_events = [event for event in explain if event.get("event") == "closed_loop_apply_result"]
    assert apply_events
    payload = apply_events[-1].get("payload") or {}
    assert payload.get("kill_switch_active") is True
    assert payload.get("apply_blocked_reason") == "kill_switch_active"
    assert payload.get("kill_switch_signal") == "env:MODEKEEPER_KILL_SWITCH"


def test_closed_loop_watch_apply_kill_switch_at_entrypoint(tmp_path: Path, mk_path: Path) -> None:
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
    assert cp.stderr.strip() == "ERROR: MODEKEEPER_KILL_SWITCH=1 blocks apply/mutate operations"
    assert not (out_dir / "iter_0001").exists()
    latest = json.loads((out_dir / "watch_latest.json").read_text(encoding="utf-8"))
    assert latest.get("apply_blocked_reason") == "kill_switch_active"
