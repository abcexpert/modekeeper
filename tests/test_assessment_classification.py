import json
import subprocess
from pathlib import Path

from modekeeper.cli import _build_assessment_fields


def _run(mk: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run([str(mk), *args], text=True, capture_output=True, check=False)


def test_eval_file_reports_insufficient_evidence_for_low_samples(tmp_path: Path, mk_path: Path) -> None:
    observe_path = tmp_path / "observe.jsonl"
    observe_path.write_text(
        "\n".join(
            [
                '{"ts":"2026-01-01T00:00:00Z","step_time_ms":100,"loss":1.0}',
                '{"ts":"2026-01-01T00:00:01Z","step_time_ms":100,"loss":1.0}',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    out_dir = tmp_path / "eval_out"

    cp = _run(
        mk_path,
        [
            "eval",
            "file",
            "--path",
            str(observe_path),
            "--out",
            str(out_dir),
        ],
    )
    assert cp.returncode == 0, cp.stderr

    latest = json.loads((out_dir / "eval_latest.json").read_text(encoding="utf-8"))
    assert latest.get("assessment_result_class") == "insufficient_evidence"
    assert latest.get("coverage_ok") is False
    assert latest.get("sample_count") == 2
    assert latest.get("window_s") == 1
    assert latest.get("signal_count") == 0
    assert latest.get("actionable_proposal_count") == 0
    reasons = latest.get("insufficient_evidence_reasons") or []
    assert "sample_count_too_low" in reasons

    summary = (out_dir / "eval_summary.md").read_text(encoding="utf-8")
    assert "assessment_result_class: insufficient_evidence" in summary
    assert "coverage_ok: False" in summary


def test_closed_loop_watch_surfaces_assessment_fields(tmp_path: Path, mk_path: Path) -> None:
    observe_path = tmp_path / "observe.jsonl"
    observe_path.write_text(
        "\n".join(
            [
                '{"ts":"2026-01-01T00:00:00Z","step_time_ms":100,"loss":1.0}',
                '{"ts":"2026-01-01T00:00:01Z","step_time_ms":100,"loss":1.0}',
                '{"ts":"2026-01-01T00:00:02Z","step_time_ms":100,"loss":1.0}',
                '{"ts":"2026-01-01T00:00:03Z","step_time_ms":100,"loss":1.0}',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    out_dir = tmp_path / "watch_out"

    cp = _run(
        mk_path,
        [
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
            "1",
            "--interval",
            "0s",
        ],
    )
    assert cp.returncode == 0, cp.stderr

    watch = json.loads((out_dir / "watch_latest.json").read_text(encoding="utf-8"))
    assert watch.get("assessment_result_class") == "no_actionable_signal"
    assert watch.get("coverage_ok") is True
    assert watch.get("sample_count") == 4
    assert watch.get("window_s") == 3
    assert watch.get("signal_count") == 0
    assert watch.get("actionable_proposal_count") == 0

    summary = (out_dir / "watch_summary.md").read_text(encoding="utf-8")
    assert "assessment_result_class: no_actionable_signal" in summary
    assert "coverage_ok: True" in summary


def test_handoff_pack_includes_assessment_fields(tmp_path: Path, mk_path: Path) -> None:
    in_dir = tmp_path / "in"
    (in_dir / "preflight").mkdir(parents=True)
    (in_dir / "eval").mkdir(parents=True)
    (in_dir / "watch").mkdir(parents=True)
    (in_dir / "roi").mkdir(parents=True)

    (in_dir / "preflight" / "preflight_latest.json").write_text(json.dumps({"ok": True}) + "\n", encoding="utf-8")
    (in_dir / "eval" / "eval_latest.json").write_text(
        json.dumps(
            {
                "sample_count": 8,
                "assessment_result_class": "signal_found",
                "coverage_ok": True,
                "window_s": 60,
                "sources_seen": ["metrics_window", "k8s_telemetry"],
                "evidence_quality": "medium",
                "insufficient_evidence_reasons": [],
                "signal_count": 1,
                "actionable_proposal_count": 1,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (in_dir / "watch" / "watch_latest.json").write_text(
        json.dumps({"duration_s": 1, "iterations_done": 1, "proposed_total": 0, "blocked_total": 0, "applied_total": 0})
        + "\n",
        encoding="utf-8",
    )
    (in_dir / "roi" / "roi_latest.json").write_text(
        json.dumps({"ok": True, "opportunity_hours_est": 0, "proposed_actions_count": 1, "top_blocker": "n/a"}) + "\n",
        encoding="utf-8",
    )

    out_dir = tmp_path / "out"
    cp = _run(mk_path, ["export", "handoff-pack", "--in", str(in_dir), "--out", str(out_dir)])
    assert cp.returncode == 0, cp.stderr

    manifest = json.loads((out_dir / "handoff_manifest.json").read_text(encoding="utf-8"))
    assessment = manifest.get("assessment")
    assert isinstance(assessment, dict)
    assert assessment.get("assessment_result_class") == "signal_found"
    assert assessment.get("coverage_ok") is True
    assert assessment.get("signal_count") == 1
    assert assessment.get("actionable_proposal_count") == 1

    summary = (out_dir / "handoff_summary.md").read_text(encoding="utf-8")
    assert "assessment_result_class: signal_found" in summary
    assert "assessment.signal_count: 1" in summary


def test_build_assessment_fields_does_not_require_loss_for_signal_found() -> None:
    assessment = _build_assessment_fields(
        sample_count=4,
        window_s=30,
        sources_seen=["metrics_window", "k8s_telemetry", "kube_object_context"],
        signal_count=1,
        actionable_proposal_count=2,
        signals={"notes": ["loss_missing"]},
    )

    assert assessment.get("assessment_result_class") == "signal_found"
    assert assessment.get("coverage_ok") is True
    assert "missing_required_evidence_family:loss" not in (assessment.get("insufficient_evidence_reasons") or [])


def test_build_assessment_fields_still_requires_core_coverage() -> None:
    assessment = _build_assessment_fields(
        sample_count=4,
        window_s=30,
        sources_seen=["k8s_telemetry"],
        signal_count=1,
        actionable_proposal_count=2,
        signals={"notes": ["loss_missing"]},
    )

    assert assessment.get("assessment_result_class") == "insufficient_evidence"
    reasons = assessment.get("insufficient_evidence_reasons") or []
    assert "missing_required_evidence_family:metrics_window" in reasons
