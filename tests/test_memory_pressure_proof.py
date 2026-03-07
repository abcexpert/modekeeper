import json
import subprocess
from pathlib import Path


def test_closed_loop_memory_pressure_synthetic_produces_non_zero_proof(
    tmp_path: Path, mk_path: Path
) -> None:
    out_dir = tmp_path / "proof_memory_pressure"
    cp = subprocess.run(
        [
            str(mk_path),
            "closed-loop",
            "run",
            "--scenario",
            "memory_pressure",
            "--dry-run",
            "--out",
            str(out_dir),
        ],
        text=True,
        capture_output=True,
        check=False,
    )
    assert cp.returncode == 0, cp.stderr

    latest = json.loads((out_dir / "closed_loop_latest.json").read_text(encoding="utf-8"))
    assert latest.get("assessment_result_class") == "signal_found"
    assert latest.get("signal_count", 0) > 0
    assert latest.get("actionable_proposal_count", 0) > 0
    assert latest.get("k8s_plan_items", 0) > 0

    summary = (out_dir / "summary.md").read_text(encoding="utf-8")
    assert "assessment_result_class: signal_found" in summary
    assert "signal_count: " in summary
    assert "actionable_proposal_count: " in summary
