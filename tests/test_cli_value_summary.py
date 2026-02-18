from __future__ import annotations

import json
import subprocess
from pathlib import Path


def test_closed_loop_latest_contains_value_summary(tmp_path: Path, mk_path: Path) -> None:
    out_dir = tmp_path / "out"
    observe_path = Path("tests/data/observe/bursty.jsonl")

    cp = subprocess.run(
        [
            str(mk_path),
            "closed-loop",
            "run",
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
    latest_path = out_dir / "closed_loop_latest.json"
    assert latest_path.exists()

    latest = json.loads(latest_path.read_text(encoding="utf-8"))
    value_summary = latest.get("value_summary")
    assert isinstance(value_summary, dict)
    assert value_summary.get("schema_version") == "value_summary.v0"
