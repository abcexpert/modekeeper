import json
import subprocess
from pathlib import Path


def test_mk093_eval_file_outputs_expected_fields(tmp_path: Path, mk_path: Path) -> None:
    out_dir = tmp_path / "eval_out"
    observe_path = Path("docs/evidence/mk092_quickstart/observe_mixed_env.jsonl")

    cp = subprocess.run(
        [
            str(mk_path),
            "eval",
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

    latest_path = out_dir / "eval_latest.json"
    summary_path = out_dir / "eval_summary.md"
    assert latest_path.exists()
    assert summary_path.exists()

    latest = json.loads(latest_path.read_text(encoding="utf-8"))
    assert latest.get("schema_version") == "eval.v0"
    assert latest.get("source") == "file"
    assert latest.get("read_only") is True
    assert latest.get("apply_requested") is False
    assert latest.get("dry_run") is True
    assert latest.get("verify_ok") is None
    assert latest.get("top_blocker") is None
    sample_count = latest.get("sample_count")
    assert isinstance(sample_count, int)
    assert sample_count > 0
    assert latest.get("telemetry_points_included") is False
    assert latest.get("proposed_actions_count") == 1

    environment = latest.get("environment")
    assert isinstance(environment, dict)
    assert environment.get("unstable") is True
    assert environment.get("nodes_seen") == ["node-a", "node-b"]
    assert environment.get("gpu_models_seen") == ["A100", "T4"]

    artifacts = latest.get("artifacts")
    assert isinstance(artifacts, dict)
    assert artifacts.get("eval_latest_path") == str(out_dir / "eval_latest.json")
    assert artifacts.get("eval_summary_path") == str(out_dir / "eval_summary.md")
    assert artifacts.get("observe_input_path") == str(observe_path)

    summary_text = summary_path.read_text(encoding="utf-8")
    assert "verify_ok: n/a" in summary_text
    assert "top_blocker: n/a" in summary_text
    assert "environment.unstable: True" in summary_text
    assert f"sample_count: {sample_count}" in summary_text
    assert "proposed_actions_count: 1" in summary_text
    assert f"artifact.eval_latest_path: {out_dir / 'eval_latest.json'}" in summary_text

    stdout = cp.stdout.strip()
    assert "verify_ok=n/a" in stdout
    assert "top_blocker=n/a" in stdout
    assert f"sample_count={sample_count}" in stdout
    assert "proposed_actions_count=1" in stdout
