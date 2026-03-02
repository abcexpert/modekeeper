import json
import subprocess
from pathlib import Path


def _write_step_time_jsonl(path: Path, values: list[float]) -> None:
    rows = [
        {"ts": 1_700_000_000 + idx, "step_time_ms": value}
        for idx, value in enumerate(values)
    ]
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


def test_roi_before_after_savings_positive(tmp_path: Path, mk_path: Path) -> None:
    baseline_path = tmp_path / "baseline.jsonl"
    candidate_path = tmp_path / "candidate.jsonl"
    out_dir = tmp_path / "out"
    _write_step_time_jsonl(baseline_path, [100, 100, 100])
    _write_step_time_jsonl(candidate_path, [50, 50, 50])

    cp = subprocess.run(
        [
            str(mk_path),
            "roi",
            "before-after",
            "--baseline-path",
            str(baseline_path),
            "--candidate-path",
            str(candidate_path),
            "--out",
            str(out_dir),
        ],
        text=True,
        capture_output=True,
    )
    assert cp.returncode == 0, cp.stderr

    latest = out_dir / "roi_before_after_latest.json"
    assert latest.exists()
    assert list(out_dir.glob("roi_before_after_*.json"))

    payload = json.loads(latest.read_text(encoding="utf-8"))
    summary = payload.get("summary", {})
    assert float(summary.get("speedup_p50")) == 2.0
    assert float(summary.get("usd_saved_per_hour")) > 0.0


def test_roi_before_after_no_savings_when_no_speedup(tmp_path: Path, mk_path: Path) -> None:
    baseline_path = tmp_path / "baseline.jsonl"
    candidate_path = tmp_path / "candidate.jsonl"
    out_dir = tmp_path / "out"
    _write_step_time_jsonl(baseline_path, [100, 100, 100])
    _write_step_time_jsonl(candidate_path, [100, 100, 100])

    cp = subprocess.run(
        [
            str(mk_path),
            "roi",
            "before-after",
            "--baseline-path",
            str(baseline_path),
            "--candidate-path",
            str(candidate_path),
            "--out",
            str(out_dir),
        ],
        text=True,
        capture_output=True,
    )
    assert cp.returncode == 0, cp.stderr

    payload = json.loads((out_dir / "roi_before_after_latest.json").read_text(encoding="utf-8"))
    summary = payload.get("summary", {})
    assert float(summary.get("speedup_p50")) <= 1.0
    assert float(summary.get("usd_saved_per_hour")) == 0.0


def test_roi_before_after_help_is_wired(mk_path: Path) -> None:
    roi_help = subprocess.run(
        [str(mk_path), "roi", "--help"],
        text=True,
        capture_output=True,
    )
    assert roi_help.returncode == 0, roi_help.stderr
    assert "before-after" in roi_help.stdout

    before_after_help = subprocess.run(
        [str(mk_path), "roi", "before-after", "--help"],
        text=True,
        capture_output=True,
    )
    assert before_after_help.returncode == 0, before_after_help.stderr
    help_text = " ".join(before_after_help.stdout.split())
    assert "--baseline-path" in help_text
    assert "--candidate-path" in help_text
    assert "--usd-per-gpu-hour" in help_text
    assert "default: 2.0" in help_text
    assert "--gpus" in help_text
    assert "default: 1" in help_text
    assert "--hours-per-month" in help_text
    assert "default: 730" in help_text
