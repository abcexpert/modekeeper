import json
import subprocess
from pathlib import Path


def test_closed_loop_watch_dry_run(tmp_path: Path, mk_path: Path) -> None:
    out_dir = tmp_path / "watch_out"
    observe_path = tmp_path / "observe.jsonl"
    _write_observe_jsonl(observe_path)
    cp = subprocess.run(
        [
            str(mk_path),
            "closed-loop",
            "watch",
            "--scenario",
            "drift",
            "--dry-run",
            "--observe-source",
            "file",
            "--observe-path",
            str(observe_path),
            "--out",
            str(out_dir),
            "--max-iterations",
            "2",
            "--interval",
            "0s",
        ],
        text=True,
        capture_output=True,
    )
    assert cp.returncode == 0

    iter_1 = out_dir / "iter_0001"
    iter_2 = out_dir / "iter_0002"
    assert iter_1.exists()
    assert iter_2.exists()


def _write_observe_jsonl(path: Path) -> None:
    rows = [
        '{"ts":"2026-01-01T00:00:00Z","step_time_ms":100,"loss":1.0}',
        '{"ts":"2026-01-01T00:00:01Z","step_time_ms":100,"loss":1.0}',
        '{"ts":"2026-01-01T00:00:02Z","step_time_ms":100,"loss":1.0}',
        '{"ts":"2026-01-01T00:00:03Z","step_time_ms":100,"loss":1.0}',
    ]
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")


def test_closed_loop_watch_apply_requires_pro(tmp_path: Path, mk_path: Path) -> None:
    out_dir = tmp_path / "watch_out"
    observe_path = tmp_path / "observe.jsonl"
    _write_observe_jsonl(observe_path)

    cp = subprocess.run(
        [
            str(mk_path),
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
            "2",
            "--interval",
            "0s",
        ],
        text=True,
        capture_output=True,
    )
    assert cp.returncode == 2
    assert cp.stderr.strip() == "PRO REQUIRED: closed-loop watch --apply"
    assert not (out_dir / "iter_0001").exists()

    watch = json.loads((out_dir / "watch_latest.json").read_text(encoding="utf-8"))
    assert watch.get("iterations_done") == 0
    assert watch.get("apply_blocked_reason") == "pro_required"
