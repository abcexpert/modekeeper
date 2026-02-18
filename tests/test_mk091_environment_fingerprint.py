import json
import subprocess
from pathlib import Path


def _write_mixed_environment_jsonl(path: Path) -> None:
    rows = [
        {
            "ts": "2026-02-13T00:00:00Z",
            "step_time_ms": 120,
            "loss": 1.0,
            "node": "node-a",
            "gpu_model": "T4",
        },
        {
            "ts": "2026-02-13T00:00:01Z",
            "step_time_ms": 121,
            "loss": 0.99,
            "node_name": "node-b",
            "gpu_name": "T4",
        },
        {
            "ts": "2026-02-13T00:00:02Z",
            "step_time_ms": 122,
            "loss": 0.98,
            "node": "node-b",
            "gpu_model": "A100",
        },
        {
            "ts": "2026-02-13T00:00:03Z",
            "step_time_ms": 123,
            "loss": 0.97,
        },
    ]
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")


def _assert_environment_and_points(report: dict) -> None:
    environment = report.get("environment")
    assert isinstance(environment, dict)
    assert environment.get("nodes_seen") == ["node-a", "node-b"]
    assert environment.get("gpu_models_seen") == ["A100", "T4"]
    assert environment.get("unstable") is True
    notes = environment.get("notes")
    assert isinstance(notes, list)
    assert "multiple_nodes_seen" in notes
    assert "multiple_gpu_models_seen" in notes

    telemetry = report.get("telemetry")
    assert isinstance(telemetry, dict)
    points = telemetry.get("points")
    assert isinstance(points, list)
    assert len(points) == 4

    saw_node = False
    saw_gpu_model = False
    saw_missing_optional = False
    for point in points:
        assert isinstance(point, dict)
        assert isinstance(point.get("ts_ms"), int)
        if "node" in point:
            saw_node = True
            assert isinstance(point.get("node"), str)
        if "gpu_model" in point:
            saw_gpu_model = True
            assert isinstance(point.get("gpu_model"), str)
        if "node" not in point and "gpu_model" not in point:
            saw_missing_optional = True
    assert saw_node
    assert saw_gpu_model
    assert saw_missing_optional


def test_mk091_observe_file_environment_fingerprint_unstable(tmp_path: Path, mk_path: Path) -> None:
    observe_path = tmp_path / "mixed_env.jsonl"
    _write_mixed_environment_jsonl(observe_path)
    out_dir = tmp_path / "observe_out"

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
    _assert_environment_and_points(report)


def test_mk091_closed_loop_file_environment_fingerprint_unstable(tmp_path: Path, mk_path: Path) -> None:
    observe_path = tmp_path / "mixed_env.jsonl"
    _write_mixed_environment_jsonl(observe_path)
    out_dir = tmp_path / "closed_loop_out"

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
    _assert_environment_and_points(report)
