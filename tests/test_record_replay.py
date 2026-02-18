import json
import subprocess
from pathlib import Path


def _data_path(name: str) -> Path:
    return Path(__file__).resolve().parent / "data" / "observe" / name


def _assert_report_basics(report: dict) -> None:
    assert report.get("schema_version") == "v0"
    duration = report.get("duration_s")
    assert isinstance(duration, int)
    assert duration >= 0


def test_closed_loop_run_replay_stable_trace_noop_plan(tmp_path: Path, mk_path: Path) -> None:
    out_dir = tmp_path / "closed_loop_out"
    observe_path = _data_path("stable.jsonl")

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

    latest_path = out_dir / "closed_loop_latest.json"
    assert latest_path.exists()
    latest = json.loads(latest_path.read_text(encoding="utf-8"))
    _assert_report_basics(latest)
    assert latest.get("apply_requested") is False
    assert latest.get("dry_run") is True
    assert latest.get("proposed") == []

    script_text = (out_dir / "k8s_plan.kubectl.sh").read_text(encoding="utf-8")
    assert "kubectl" not in script_text


def test_closed_loop_watch_replay_bursty_trace_rollups(tmp_path: Path, mk_path: Path) -> None:
    out_dir = tmp_path / "watch_out"
    observe_path = _data_path("bursty.jsonl")

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

    rep1 = json.loads((iter_1 / "closed_loop_latest.json").read_text(encoding="utf-8"))
    rep2 = json.loads((iter_2 / "closed_loop_latest.json").read_text(encoding="utf-8"))
    _assert_report_basics(rep1)
    _assert_report_basics(rep2)

    watch_path = out_dir / "watch_latest.json"
    assert watch_path.exists()
    watch = json.loads(watch_path.read_text(encoding="utf-8"))
    _assert_report_basics(watch)
    assert watch.get("iterations_done") == 2
    assert watch.get("last_iteration_out_dir") == str(iter_2)

    proposed_total = len(rep1.get("proposed", [])) + len(rep2.get("proposed", []))
    assert watch.get("proposed_total") == proposed_total
    assert watch.get("dry_run_total") == 2


def test_closed_loop_run_replay_sparse_trace_reports(tmp_path: Path, mk_path: Path) -> None:
    out_dir = tmp_path / "sparse_out"
    observe_path = _data_path("sparse.jsonl")

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

    latest_path = out_dir / "closed_loop_latest.json"
    assert latest_path.exists()
    latest = json.loads(latest_path.read_text(encoding="utf-8"))
    _assert_report_basics(latest)
    assert isinstance(latest.get("proposed", []), list)


def test_closed_loop_run_replay_out_of_order_trace_reports(tmp_path: Path, mk_path: Path) -> None:
    out_dir = tmp_path / "out_of_order_out"
    observe_path = _data_path("out_of_order.jsonl")

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

    latest_path = out_dir / "closed_loop_latest.json"
    assert latest_path.exists()
    latest = json.loads(latest_path.read_text(encoding="utf-8"))
    _assert_report_basics(latest)
    assert isinstance(latest.get("proposed", []), list)


def test_closed_loop_watch_replay_out_of_order_trace_reports(tmp_path: Path, mk_path: Path) -> None:
    out_dir = tmp_path / "out_of_order_watch_out"
    observe_path = _data_path("out_of_order.jsonl")

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

    watch_path = out_dir / "watch_latest.json"
    assert watch_path.exists()
    watch = json.loads(watch_path.read_text(encoding="utf-8"))
    _assert_report_basics(watch)
    assert watch.get("iterations_done") == 2


def test_closed_loop_run_replay_dirty_traces(tmp_path: Path, mk_path: Path) -> None:
    traces = [
        "corrupted.jsonl",
        "duplicates.jsonl",
        "clock_skew.jsonl",
    ]
    for name in traces:
        out_dir = tmp_path / f"dirty_{name.replace('.jsonl', '')}"
        observe_path = _data_path(name)
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

        latest_path = out_dir / "closed_loop_latest.json"
        assert latest_path.exists()
        latest = json.loads(latest_path.read_text(encoding="utf-8"))
        _assert_report_basics(latest)
        assert isinstance(latest.get("proposed", []), list)
        if name == "corrupted.jsonl":
            observe_ingest = latest.get("observe_ingest", {})
            assert observe_ingest.get("dropped_total", 0) > 0


def test_closed_loop_watch_replay_corrupted_trace_observe_ingest_rollup(
    tmp_path: Path, mk_path: Path
) -> None:
    out_dir = tmp_path / "corrupted_watch_out"
    observe_path = _data_path("corrupted.jsonl")

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

    watch_path = out_dir / "watch_latest.json"
    summary_path = out_dir / "watch_summary.md"
    assert watch_path.exists()
    assert summary_path.exists()

    iter_1 = out_dir / "iter_0001" / "closed_loop_latest.json"
    iter_2 = out_dir / "iter_0002" / "closed_loop_latest.json"
    assert iter_1.exists()
    assert iter_2.exists()

    rep1 = json.loads(iter_1.read_text(encoding="utf-8"))
    rep2 = json.loads(iter_2.read_text(encoding="utf-8"))
    observe_1 = rep1.get("observe_ingest", {})
    observe_2 = rep2.get("observe_ingest", {})

    totals: dict[str, int] = {}
    for observe in (observe_1, observe_2):
        if isinstance(observe, dict):
            for key, value in observe.items():
                if isinstance(value, int):
                    totals[key] = totals.get(key, 0) + value

    watch = json.loads(watch_path.read_text(encoding="utf-8"))
    _assert_report_basics(watch)
    artifact_paths = watch.get("artifact_paths")
    assert isinstance(artifact_paths, dict)
    assert artifact_paths.get("watch_latest_path") == str(watch_path)
    assert artifact_paths.get("watch_summary_path") == str(summary_path)
    assert artifact_paths.get("last_iteration_report_path") == str(iter_2)
    assert artifact_paths.get("last_iteration_explain_path") == str(
        out_dir / "iter_0002" / "explain.jsonl"
    )
    watch_observe = watch.get("observe_ingest")
    assert isinstance(watch_observe, dict)
    for key, value in totals.items():
        assert watch_observe.get(key) == value

    summary_path = out_dir / "watch_summary.md"
    assert summary_path.exists()
    summary = summary_path.read_text(encoding="utf-8")
    assert f"watch_latest_path: {out_dir / 'watch_latest.json'}" in summary
    assert "last_iteration_report_path:" in summary
    assert "last_iteration_explain_path:" in summary


def test_watch_summary_null_last_iteration_paths(tmp_path: Path) -> None:
    from modekeeper.cli import _write_watch_latest, _write_watch_summary

    out_dir = tmp_path / "watch_null_out"
    out_dir.mkdir()
    report = {
        "schema_version": "v0",
        "started_at": "2024-01-01T00:00:00Z",
        "finished_at": "2024-01-01T00:00:01Z",
        "duration_s": 1,
        "interval_s": 0,
        "max_iterations": 0,
        "iterations_done": 0,
        "last_iteration_out_dir": None,
        "proposed_total": 0,
        "applied_total": 0,
        "blocked_total": 0,
        "verify_failed_total": 0,
        "dry_run_total": 0,
        "apply_attempted_total": 0,
        "apply_ok_total": 0,
        "apply_failed_total": 0,
        "artifact_paths": {
            "watch_latest_path": str(out_dir / "watch_latest.json"),
            "watch_summary_path": str(out_dir / "watch_summary.md"),
            "last_iteration_report_path": None,
            "last_iteration_explain_path": None,
        },
    }

    _write_watch_latest(out_dir, report)
    _write_watch_summary(out_dir, report)

    watch = json.loads((out_dir / "watch_latest.json").read_text(encoding="utf-8"))
    artifact_paths = watch.get("artifact_paths")
    assert isinstance(artifact_paths, dict)
    assert artifact_paths.get("last_iteration_report_path") is None
    assert artifact_paths.get("last_iteration_explain_path") is None

    summary = (out_dir / "watch_summary.md").read_text(encoding="utf-8")
    assert f"watch_latest_path: {out_dir / 'watch_latest.json'}" in summary
    assert f"watch_summary_path: {out_dir / 'watch_summary.md'}" in summary
    assert "last_iteration_report_path: null" in summary
    assert "last_iteration_explain_path: null" in summary
def test_closed_loop_watch_replay_realistic_dirty_trace_reports(tmp_path: Path, mk_path: Path) -> None:
    out_dir = tmp_path / "realistic_dirty_watch_out"
    observe_path = _data_path("realistic_dirty.jsonl")

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
            "3",
            "--interval",
            "0s",
        ],
        text=True,
        capture_output=True,
    )
    assert cp.returncode == 0, cp.stderr

    watch_path = out_dir / "watch_latest.json"
    summary_path = out_dir / "watch_summary.md"
    assert watch_path.exists()
    assert summary_path.exists()

    watch = json.loads(watch_path.read_text(encoding="utf-8"))
    _assert_report_basics(watch)
    assert watch.get("iterations_done") == 3
    assert watch.get("dry_run_total") == 3

    observe_ingest = watch.get("observe_ingest")
    assert isinstance(observe_ingest, dict)
    assert observe_ingest.get("dropped_total", 0) > 0

    artifact_paths = watch.get("artifact_paths")
    assert isinstance(artifact_paths, dict)
    assert artifact_paths.get("watch_latest_path") == str(watch_path)
    assert artifact_paths.get("watch_summary_path") == str(summary_path)

    iter_3_report = out_dir / "iter_0003" / "closed_loop_latest.json"
    iter_3_explain = out_dir / "iter_0003" / "explain.jsonl"
    assert artifact_paths.get("last_iteration_report_path") == str(iter_3_report)
    assert artifact_paths.get("last_iteration_explain_path") == str(iter_3_explain)


def test_closed_loop_watch_replay_record_raw(tmp_path: Path, mk_path: Path) -> None:
    out_dir = tmp_path / "raw_watch_out"
    observe_path = _data_path("realistic_dirty.jsonl")
    record_raw_path = tmp_path / "raw.jsonl"

    cp = subprocess.run(
        [
            str(mk_path),
            "closed-loop",
            "watch",
            "--dry-run",
            "--scenario",
            "drift",
            "--observe-source",
            "file",
            "--observe-path",
            str(observe_path),
            "--observe-record-raw",
            str(record_raw_path),
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

    watch_path = out_dir / "watch_latest.json"
    assert watch_path.exists()
    watch = json.loads(watch_path.read_text(encoding="utf-8"))
    assert watch.get("schema_version") == "v0"
    assert isinstance(watch.get("duration_s"), int)

    assert record_raw_path.exists()
    assert record_raw_path.stat().st_size > 0
