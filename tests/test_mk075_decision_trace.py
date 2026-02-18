import json
import subprocess
from pathlib import Path


def test_closed_loop_writes_decision_trace_jsonl(tmp_path: Path, mk_path: Path) -> None:
    out_dir = tmp_path / "closed_loop_out"
    observe_path = Path(__file__).resolve().parent / "data" / "observe" / "bursty.jsonl"

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
    assert cp.returncode == 0

    trace_path = out_dir / "decision_trace_latest.jsonl"
    assert trace_path.exists()

    required_keys = {
        "schema_version",
        "tick",
        "mode",
        "signals",
        "chord",
        "actions",
        "results",
    }
    lines = trace_path.read_text(encoding="utf-8").splitlines()
    assert lines
    for line in lines:
        event = json.loads(line)
        assert isinstance(event, dict)
        assert required_keys.issubset(event.keys())
        assert event.get("schema_version") == "decision_trace_event.v0"

    latest = json.loads((out_dir / "closed_loop_latest.json").read_text(encoding="utf-8"))
    audit_trace = latest.get("audit_trace")
    assert isinstance(audit_trace, dict)
    assert audit_trace.get("path") == "decision_trace_latest.jsonl"
    assert audit_trace.get("schema_version") == "decision_trace_event.v0"

