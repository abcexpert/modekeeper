from modekeeper.core.analysis import analyze_signals
from modekeeper.telemetry.k8s_log_source import parse_k8s_log_lines


def test_k8s_log_parses_gpu_fields_and_sets_signal() -> None:
    lines = [
        '{"ts": 1700000000000, "step_time_ms": 10, "loss": 1.0, "gpu_util_pct": 95, "gpu_mem_util_pct": 10}'
    ]
    samples = parse_k8s_log_lines(lines)
    assert len(samples) == 1
    s = samples[0]
    assert s.gpu_util_pct == 95.0
    assert s.gpu_mem_util_pct == 10.0

    signals = analyze_signals(samples)
    assert signals.get("gpu_saturated") is True
    assert "gpu_saturated" in (signals.get("notes") or [])


def test_gpu_mem_used_total_derives_util_pct() -> None:
    lines = [
        '{"ts": 1700000000000, "step_time_ms": 10, "loss": 1.0, "gpu_mem_used_mb": 9500, "gpu_mem_total_mb": 10000}'
    ]
    samples = parse_k8s_log_lines(lines)
    assert len(samples) == 1
    assert samples[0].gpu_mem_util_pct == 95.0
    signals = analyze_signals(samples)
    assert signals.get("gpu_saturated") is True
