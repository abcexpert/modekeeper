import json
import subprocess
from pathlib import Path


def test_mk096_roi_report_builds_artifacts_and_summary(tmp_path: Path, mk_path: Path) -> None:
    inputs_dir = tmp_path / "inputs"
    out_dir = tmp_path / "roi_out"
    inputs_dir.mkdir(parents=True, exist_ok=True)

    preflight_path = inputs_dir / "preflight_latest.json"
    eval_path = inputs_dir / "eval_latest.json"
    watch_path = inputs_dir / "watch_latest.json"
    last_iter_report_path = inputs_dir / "closed_loop_latest.json"

    preflight_path.write_text(
        json.dumps(
            {
                "schema_version": "preflight.v0",
                "ok": True,
                "top_blocker": None,
                "gpu_capacity_present": False,
                "nvidia_device_plugin_present": False,
                "deploy_gpu_request": 0,
                "notes": ["gpu_not_in_cluster", "device_plugin_missing", "deploy_not_requesting_gpu"],
            },
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    eval_path.write_text(
        json.dumps(
            {
                "schema_version": "eval.v0",
                "top_blocker": None,
                "environment": {
                    "unstable": False,
                    "nodes_seen": ["node-a"],
                    "gpu_models_seen": ["A100"],
                    "notes": [],
                },
                "signals": {"notes": ["loss_missing"]},
            },
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    watch_path.write_text(
        json.dumps(
            {
                "schema_version": "v0",
                "duration_s": 120,
                "iterations_done": 4,
                "interval_s": 30,
                "proposed_total": 0,
                "applied_total": 0,
                "blocked_total": 0,
                "last_iteration_out_dir": str(inputs_dir / "iter_0004"),
                "artifact_paths": {
                    "last_iteration_report_path": str(last_iter_report_path),
                },
            },
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    last_iter_report_path.write_text(
        json.dumps(
            {
                "schema_version": "v0",
                "opportunity_hours_est": 12.5,
                "proposed_actions_count": 2,
                "signals": {"notes": ["loss_missing"]},
            },
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    cp = subprocess.run(
        [
            str(mk_path),
            "roi",
            "report",
            "--preflight",
            str(preflight_path),
            "--eval",
            str(eval_path),
            "--watch",
            str(watch_path),
            "--out",
            str(out_dir),
        ],
        text=True,
        capture_output=True,
    )
    assert cp.returncode == 0, cp.stderr

    roi_latest = out_dir / "roi_latest.json"
    roi_summary = out_dir / "roi_summary.md"
    explain = out_dir / "explain.jsonl"
    assert roi_latest.exists()
    assert roi_summary.exists()
    assert explain.exists()

    latest = json.loads(roi_latest.read_text(encoding="utf-8"))
    assert latest.get("schema_version") == "roi.v0"
    assert latest.get("ok") is False
    assert latest.get("top_blocker") == "loss_missing"
    assert latest.get("opportunity_hours_est") == 12.5
    assert latest.get("proposed_actions_count") == 2
    key_artifacts = latest.get("key_artifacts")
    assert isinstance(key_artifacts, list)
    assert str(roi_latest) in key_artifacts
    assert str(roi_summary) in key_artifacts
    assert str(explain) in key_artifacts

    summary_text = roi_summary.read_text(encoding="utf-8")
    assert "ok: false" in summary_text
    assert "top_blocker: loss_missing" in summary_text
    assert "opportunity_hours_est: 12.5" in summary_text
    assert "watch.iterations_done: 4" in summary_text
    assert "watch.proposed_total: 0" in summary_text
    assert "watch.applied_total: 0" in summary_text
    assert "watch.blocked_total: 0" in summary_text

    stdout = cp.stdout.strip()
    assert "roi_ok=false" in stdout
    assert "top_blocker=loss_missing" in stdout
    assert "opportunity_hours_est=12.5" in stdout
    assert f"roi={roi_latest}" in stdout
    assert f"summary={roi_summary}" in stdout
