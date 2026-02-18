from modekeeper.core.summary import summarize_observe


def test_summary_empty_signals() -> None:
    summary = summarize_observe({})
    assert summary["money_leak_risk"] == "low"
    assert summary["top_symptoms"] in ([], ())
    assert any("не обнаружено" in rec for rec in summary["recommendations"])


def test_summary_drift_detected() -> None:
    summary = summarize_observe({"drift": True})
    assert summary["money_leak_risk"] in ("medium", "high")
    assert "drift" in summary["top_symptoms"]


def test_summary_drift_straggler_high() -> None:
    summary = summarize_observe({"drift": True, "straggler": {"detected": True}})
    assert summary["money_leak_risk"] == "high"
