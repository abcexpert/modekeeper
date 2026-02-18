import json
import subprocess
from pathlib import Path


def test_closed_loop_run_with_scalar_policy_writes_latest(tmp_path: Path, mk_path: Path) -> None:
    out_dir = tmp_path / "out"
    trace_path = tmp_path / "trace.jsonl"
    trace_path.write_text(
        "\n".join(
            [
                '{"ts":"2026-01-01T00:00:00Z","step_time_ms":100,"loss":1.0}',
                '{"ts":"2026-01-01T00:00:01Z","step_time_ms":105,"loss":1.0}',
                '{"ts":"2026-01-01T00:00:02Z","step_time_ms":110,"loss":1.0}',
                '{"ts":"2026-01-01T00:00:03Z","step_time_ms":300,"loss":1.0}',
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    cp = subprocess.run(
        [
            str(mk_path),
            "closed-loop",
            "run",
            "--dry-run",
            "--policy",
            "scalar",
            "--observe-source",
            "file",
            "--observe-path",
            str(trace_path),
            "--out",
            str(out_dir),
        ],
        text=True,
        capture_output=True,
    )
    assert cp.returncode == 0

    latest_path = out_dir / "closed_loop_latest.json"
    assert latest_path.exists()
    latest = json.loads(latest_path.read_text(encoding="utf-8"))
    assert latest.get("policy") == "scalar"
