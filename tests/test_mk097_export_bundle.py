import json
import subprocess
import tarfile
from pathlib import Path


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def test_mk097_export_bundle_builds_manifest_tar_and_summary(tmp_path: Path, mk_path: Path) -> None:
    report_dir = tmp_path / "report"
    out_dir = report_dir / "bundle"
    report_dir.mkdir(parents=True, exist_ok=True)

    _write_json(
        report_dir / "preflight_latest.json",
        {"schema_version": "preflight.v0", "ok": True},
    )
    _write_json(
        report_dir / "eval_latest.json",
        {
            "schema_version": "eval.v0",
            "sample_count": 12,
            "environment": {
                "unstable": False,
                "nodes_seen": ["node-a"],
                "gpu_models_seen": ["A100"],
            },
        },
    )
    _write_json(
        report_dir / "watch_latest.json",
        {
            "schema_version": "v0",
            "duration_s": 30,
            "iterations_done": 3,
            "proposed_total": 4,
            "blocked_total": 1,
            "applied_total": 0,
        },
    )
    _write_json(
        report_dir / "roi_latest.json",
        {
            "schema_version": "roi.v0",
            "opportunity_hours_est": 8.5,
            "proposed_actions_count": 2,
            "ok": False,
            "top_blocker": "loss_missing",
        },
    )
    (report_dir / "preflight_summary.md").write_text("# preflight\n", encoding="utf-8")
    (report_dir / "eval_summary.md").write_text("# eval\n", encoding="utf-8")
    (report_dir / "watch_summary.md").write_text("# watch\n", encoding="utf-8")
    (report_dir / "roi_summary.md").write_text("# roi\n", encoding="utf-8")
    (report_dir / "explain.jsonl").write_text('{"event":"sample"}\n', encoding="utf-8")

    cp = subprocess.run(
        [
            str(mk_path),
            "export",
            "bundle",
            "--in",
            str(report_dir),
            "--out",
            str(out_dir),
        ],
        text=True,
        capture_output=True,
    )
    assert cp.returncode == 0, cp.stderr

    manifest_path = out_dir / "bundle_manifest.json"
    tar_path = out_dir / "bundle.tar.gz"
    summary_path = out_dir / "bundle_summary.md"
    assert manifest_path.exists()
    assert tar_path.exists()
    assert summary_path.exists()

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest.get("schema_version") == "bundle.v0"
    files = manifest.get("files")
    assert isinstance(files, list)
    rel_paths = [item.get("rel_path") for item in files]
    assert rel_paths == sorted(rel_paths)
    assert len(files) >= 9
    for item in files:
        digest = item.get("sha256")
        assert isinstance(digest, str)
        assert len(digest) == 64

    with tarfile.open(tar_path, "r:gz") as tar:
        names = tar.getnames()
    assert names[0] == "bundle_manifest.json"
    assert "preflight_latest.json" in names
    assert "eval_latest.json" in names
    assert "watch_latest.json" in names
    assert "roi_latest.json" in names

    summary = summary_path.read_text(encoding="utf-8")
    assert "files_count:" in summary
    assert "watch.iterations_done: 3" in summary
    assert "roi.opportunity_hours_est: 8.5" in summary
    assert "top_blocker: loss_missing" in summary

    stdout = cp.stdout.strip()
    assert "bundle_ok=true" in stdout
    assert f"manifest={manifest_path}" in stdout
    assert f"tar={tar_path}" in stdout
    assert f"summary={summary_path}" in stdout


def test_export_bundle_prefers_latest_iteration_artifacts(tmp_path: Path, mk_path: Path) -> None:
    report_dir = tmp_path / "report"
    out_dir = report_dir / "bundle"
    iter_1 = report_dir / "iter_0001"
    iter_2 = report_dir / "iter_0002"
    iter_1.mkdir(parents=True, exist_ok=True)
    iter_2.mkdir(parents=True, exist_ok=True)

    _write_json(iter_1 / "closed_loop_latest.json", {"schema_version": "closed_loop.v0", "iteration": 1})
    _write_json(iter_2 / "closed_loop_latest.json", {"schema_version": "closed_loop.v0", "iteration": 2})
    _write_json(iter_1 / "k8s_verify_latest.json", {"schema_version": "k8s_verify.v0", "iteration": 1})
    _write_json(iter_2 / "k8s_verify_latest.json", {"schema_version": "k8s_verify.v0", "iteration": 2})
    _write_json(report_dir / "preflight_latest.json", {"schema_version": "preflight.v0", "ok": True})
    _write_json(report_dir / "eval_latest.json", {"schema_version": "eval.v0", "sample_count": 1})
    _write_json(
        report_dir / "watch_latest.json",
        {
            "schema_version": "watch.v0",
            "duration_s": 1,
            "iterations_done": 2,
            "proposed_total": 0,
            "blocked_total": 0,
            "applied_total": 0,
        },
    )
    _write_json(
        report_dir / "roi_latest.json",
        {"schema_version": "roi.v0", "ok": True, "opportunity_hours_est": 0, "proposed_actions_count": 0},
    )

    cp = subprocess.run(
        [str(mk_path), "export", "bundle", "--in", str(report_dir), "--out", str(out_dir)],
        text=True,
        capture_output=True,
        check=False,
    )
    assert cp.returncode == 0, cp.stderr

    manifest = json.loads((out_dir / "bundle_manifest.json").read_text(encoding="utf-8"))
    rel_paths = {item.get("rel_path") for item in manifest.get("files", [])}
    assert "iter_0002/closed_loop_latest.json" in rel_paths
    assert "iter_0002/k8s_verify_latest.json" in rel_paths
    assert "iter_0001/closed_loop_latest.json" not in rel_paths
    assert "iter_0001/k8s_verify_latest.json" not in rel_paths
