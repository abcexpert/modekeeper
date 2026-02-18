import json
import subprocess
from pathlib import Path


def test_file_source_worker_latencies_enable_straggler_signal(tmp_path: Path, mk_path: Path) -> None:
    observe_path = tmp_path / "worker_latencies.jsonl"
    out_dir = tmp_path / "closed_loop_out"

    rows = []
    base_ts_ms = 1_700_000_000_000
    for i in range(200):
        rows.append(
            {
                "ts": base_ts_ms + i * 1000,
                "step_time_ms": 2000,
                "worker_latencies_ms": [2000, 2000, 2000, 120000],
            }
        )
    observe_path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")

    cp = subprocess.run(
        [
            str(mk_path),
            "closed-loop",
            "run",
            "--scenario",
            "drift",
            "--dry-run",
            "--observe-source",
            "file",
            "--observe-path",
            str(observe_path),
            "--out",
            str(out_dir),
        ],
        text=True,
        capture_output=True,
    )
    assert cp.returncode == 0, cp.stderr

    trace_path = out_dir / "decision_trace_latest.jsonl"
    assert trace_path.exists()
    lines = trace_path.read_text(encoding="utf-8").splitlines()
    assert lines

    event = json.loads(lines[0])
    signals = event.get("signals") or {}
    assert signals.get("straggler") is True

    actions = event.get("actions") or []
    timeout_actions = [a for a in actions if a.get("knob") == "timeout_ms"]
    assert timeout_actions
    assert any(a.get("chord") == "TIMEOUT-GUARD" for a in timeout_actions)
