import json
import subprocess
import time
from pathlib import Path


def _write_gpu_observe_jsonl(path: Path) -> None:
    rows = [
        {
            "ts": "2026-01-01T00:00:00Z",
            "step_time_ms": 120,
            "loss": 1.2,
            "gpu_util_pct": 88,
        },
        {
            "ts": "2026-01-01T00:00:01Z",
            "step_time_ms": 125,
            "loss": 1.1,
            "gpu_mem_used_mb": 9000,
            "gpu_mem_total_mb": 10000,
        },
        {
            "ts": "2026-01-01T00:00:02Z",
            "step_time_ms": 130,
            "loss": 1.0,
        },
    ]
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


def _assert_telemetry_points(payload: dict) -> None:
    telemetry = payload.get("telemetry")
    assert isinstance(telemetry, dict)
    points = telemetry.get("points")
    assert isinstance(points, list)
    assert len(points) >= 1
    for point in points:
        assert isinstance(point, dict)
        assert isinstance(point.get("ts_ms"), int)


def test_mk089_observe_file_writes_telemetry_with_gpu_fields(tmp_path: Path, mk_path: Path) -> None:
    observe_path = tmp_path / "observe_gpu.jsonl"
    out_dir = tmp_path / "observe_out"
    _write_gpu_observe_jsonl(observe_path)

    cp = subprocess.run(
        [
            str(mk_path),
            "observe",
            "--duration",
            "1s",
            "--source",
            "file",
            "--path",
            str(observe_path),
            "--out",
            str(out_dir),
        ],
        text=True,
        capture_output=True,
    )
    assert cp.returncode == 0, cp.stderr

    report = json.loads((out_dir / "observe_latest.json").read_text(encoding="utf-8"))
    _assert_telemetry_points(report)
    telemetry = report.get("telemetry") or {}
    assert telemetry.get("sample_count") == 3
    assert any(
        (point.get("gpu_util_pct") is not None) or (point.get("gpu_mem_util_pct") is not None)
        for point in telemetry.get("points", [])
    )


def test_mk089_closed_loop_file_writes_telemetry_with_timestamps(tmp_path: Path, mk_path: Path) -> None:
    observe_path = tmp_path / "observe_gpu.jsonl"
    out_dir = tmp_path / "closed_loop_out"
    _write_gpu_observe_jsonl(observe_path)

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

    report = json.loads((out_dir / "closed_loop_latest.json").read_text(encoding="utf-8"))
    _assert_telemetry_points(report)
    telemetry = report.get("telemetry") or {}
    assert telemetry.get("sample_count") == 3


def test_mk089_closed_loop_watch_sigterm_writes_final_artifacts(tmp_path: Path, mk_path: Path) -> None:
    observe_path = tmp_path / "observe_gpu.jsonl"
    out_dir = tmp_path / "watch_out"
    _write_gpu_observe_jsonl(observe_path)

    proc = subprocess.Popen(
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
            "--interval",
            "2s",
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    try:
        watch_latest = out_dir / "watch_latest.json"
        deadline = time.time() + 20.0
        saw_first_iteration = False
        while time.time() < deadline:
            if watch_latest.exists():
                try:
                    watch = json.loads(watch_latest.read_text(encoding="utf-8"))
                except json.JSONDecodeError:
                    time.sleep(0.1)
                    continue
                if isinstance(watch.get("iterations_done"), int) and watch["iterations_done"] >= 1:
                    saw_first_iteration = True
                    break
            time.sleep(0.1)
        assert saw_first_iteration, "watch_latest.json with iterations_done>=1 not observed in time"

        proc.terminate()
        proc.wait(timeout=20)
        assert proc.returncode == 0
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=10)

    watch_latest = out_dir / "watch_latest.json"
    watch_summary = out_dir / "watch_summary.md"
    assert watch_latest.exists()
    assert watch_summary.exists()
    watch = json.loads(watch_latest.read_text(encoding="utf-8"))
    assert isinstance(watch.get("iterations_done"), int)
    assert watch["iterations_done"] >= 1
