import json
import subprocess
from pathlib import Path


def test_mk068_demo_cli_deterministic_steps(tmp_path: Path, mk_path: Path) -> None:
    out_dir = tmp_path / "mk068_out"
    cp = subprocess.run(
        [
            str(mk_path),
            "demo",
            "mk068",
            "--out",
            str(out_dir),
        ],
        text=True,
        capture_output=True,
    )
    assert cp.returncode == 0

    report_path = out_dir / "mk068_demo_latest.json"
    assert report_path.exists()
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report.get("schema_version") == "mk068_demo.v0"
    assert report.get("name") == "mk068"
    assert report.get("safe") is True

    steps = report.get("timeline")
    assert isinstance(steps, list)
    assert steps
    for row in steps:
        assert "mode" in row
        assert "chord" in row
        assert "blocked_reason" in row
        assert "changed_knobs" in row
        assert isinstance(row.get("changed_knobs"), list)

    modes = [row.get("mode") for row in steps]
    assert modes == ["NORMAL", "DRIFT", "BURST", "STRAGGLER", "RECOVER", "NORMAL"]
