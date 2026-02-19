import json
import subprocess
from pathlib import Path


def test_cli_quickstart_file_source(tmp_path: Path, mk_path: Path) -> None:
    out_dir = tmp_path / "quickstart"
    observe_path = Path("docs/evidence/mk092_quickstart/observe_mixed_env.jsonl")
    assert observe_path.exists()

    cp = subprocess.run(
        [
            str(mk_path),
            "quickstart",
            "--out",
            str(out_dir),
            "--observe-source",
            "file",
            "--observe-path",
            str(observe_path),
        ],
        check=False,
        capture_output=True,
        text=True,
    )
    assert cp.returncode == 0, cp.stderr

    assert (out_dir / "summary.md").exists()

    plan_latest = out_dir / "plan" / "closed_loop_latest.json"
    assert plan_latest.exists()
    plan_report = json.loads(plan_latest.read_text(encoding="utf-8"))
    assert isinstance(plan_report.get("k8s_plan_path"), str)
    assert plan_report.get("k8s_plan_path")

    assert (out_dir / "verify" / "k8s_verify_latest.json").exists()
    assert (out_dir / "preflight" / "preflight_latest.json").exists()
    assert (out_dir / "preflight" / "summary.md").exists()
    assert (out_dir / "eval" / "eval_latest.json").exists()
    assert (out_dir / "eval" / "summary.md").exists()
    assert (out_dir / "watch" / "watch_latest.json").exists()
    assert (out_dir / "watch" / "summary.md").exists()
    assert (out_dir / "roi" / "roi_latest.json").exists()
    assert (out_dir / "roi" / "summary.md").exists()

    export_dir = out_dir / "export"
    assert (export_dir / "bundle_manifest.json").exists()
    assert (export_dir / "bundle.tar.gz").exists()
    bundle_summary = (export_dir / "bundle_summary.md").read_text(encoding="utf-8")
    assert "missing_preflight_latest.json" not in bundle_summary
    assert "missing_eval_latest.json" not in bundle_summary
    assert "missing_roi_latest.json" not in bundle_summary
    assert "missing_watch_latest.json" not in bundle_summary
