import json
import subprocess
from pathlib import Path


def test_mk080_roi_estimate_cli_non_actionable(tmp_path: Path, mk_path: Path) -> None:
    observe_path = tmp_path / "observe.jsonl"
    rows: list[dict[str, object]] = []
    for idx in range(200):
        step_time_ms = 120000 if idx % 7 == 0 else 2000
        rows.append(
            {
                "ts": 1_700_000_000 + idx,
                "step_time_ms": step_time_ms,
            }
        )
    observe_path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")

    out_dir = tmp_path / "out"
    cp = subprocess.run(
        [
            str(mk_path),
            "roi",
            "estimate",
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

    latest_path = out_dir / "roi_estimate_latest.json"
    assert latest_path.exists()

    latest = json.loads(latest_path.read_text(encoding="utf-8"))
    assert latest.get("schema_version") == "roi_estimate.v0"
    assert latest.get("summary", {}).get("samples") == 200

    potential = latest.get("potential", {})
    speedup_range = potential.get("speedup_pct_range")
    latency_range = potential.get("latency_reduction_pct_range")
    assert isinstance(speedup_range, list) and len(speedup_range) == 2
    assert isinstance(latency_range, list) and len(latency_range) == 2
    assert float(speedup_range[1]) > 0
    assert float(latency_range[1]) > 0

    text = latest_path.read_text(encoding="utf-8")
    forbidden = ["actions", "knob", "target", "chord", "k8s_plan", "decision_trace"]
    lower_text = text.lower()
    for marker in forbidden:
        assert marker not in lower_text
