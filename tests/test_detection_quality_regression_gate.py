import json
import subprocess
from pathlib import Path


_PROOF_GATE_EXPECTATIONS = {
    "replica_overprovisioning": {
        "expected_signal_flags": {"drift": True, "burst": False},
        "expected_note": "loss_drift",
        "expected_knobs": {"grad_accum_steps", "microbatch_size"},
    },
    "cpu_pressure": {
        "expected_signal_flags": {"drift": False, "burst": True},
        "expected_note": "latency_burst",
        "expected_knobs": {"dataloader_prefetch_factor", "concurrency"},
    },
    "memory_pressure": {
        "expected_signal_flags": {"drift": False, "burst": True},
        "expected_note": "latency_burst",
        "expected_knobs": {"dataloader_prefetch_factor", "concurrency"},
    },
}


def _run_scenario(mk_path: Path, tmp_path: Path, scenario: str) -> tuple[dict, dict, str]:
    out_dir = tmp_path / f"proof_gate_{scenario}"
    cp = subprocess.run(
        [
            str(mk_path),
            "closed-loop",
            "run",
            "--scenario",
            scenario,
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
    first_trace_line = (out_dir / "decision_trace_latest.jsonl").read_text(encoding="utf-8").splitlines()[0]
    first_trace = json.loads(first_trace_line)
    summary = (out_dir / "summary.md").read_text(encoding="utf-8")
    return latest, first_trace, summary


def test_detection_quality_regression_gate_across_proof_scenarios(
    tmp_path: Path, mk_path: Path
) -> None:
    # Keep gate scope pinned to post-v0.1.33 proof scenarios.
    assert set(_PROOF_GATE_EXPECTATIONS) == {
        "replica_overprovisioning",
        "cpu_pressure",
        "memory_pressure",
    }

    for scenario, expected in _PROOF_GATE_EXPECTATIONS.items():
        latest, first_trace, summary = _run_scenario(mk_path, tmp_path, scenario)

        assert latest.get("assessment_result_class") == "signal_found"
        assert latest.get("coverage_ok") is True
        assert latest.get("insufficient_evidence_reasons") == []
        assert latest.get("signal_count", 0) > 0
        assert latest.get("actionable_proposal_count", 0) > 0
        assert latest.get("k8s_plan_items", 0) > 0

        signals = first_trace.get("signals", {})
        for flag_name, expected_value in expected["expected_signal_flags"].items():
            assert signals.get(flag_name) is expected_value
        assert expected["expected_note"] in signals.get("notes", [])

        action_knobs = {a.get("knob") for a in first_trace.get("actions", []) if isinstance(a, dict)}
        assert action_knobs == expected["expected_knobs"]

        assert "assessment_result_class: signal_found" in summary
        assert "actionable_proposal_count: " in summary
