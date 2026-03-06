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


def test_k8s_log_parses_duration_seconds_key_with_kubectl_timestamp_prefix() -> None:
    lines = [
        "2026-03-06T10:11:12Z level=info latency=0.250s path=/",
        "2026-03-06T10:11:13Z level=info latency=0.300s path=/cart",
    ]
    samples = parse_k8s_log_lines(lines)
    assert len(samples) == 2
    assert samples[0].latency_ms == 250.0
    assert samples[1].latency_ms == 300.0


def test_k8s_log_parses_plain_text_duration_fallback() -> None:
    lines = [
        "2026-03-06T10:11:12Z GET / 200 took 18ms",
        "2026-03-06T10:11:13Z GET /cart 200 took 24ms",
    ]
    samples = parse_k8s_log_lines(lines)
    assert len(samples) == 2
    assert samples[0].latency_ms == 18.0
    assert samples[1].latency_ms == 24.0


def test_k8s_log_parses_nanosecond_rfc3339_prefix() -> None:
    lines = [
        '2026-03-06T20:29:52.347021290Z {"http.resp.took_ms":29}',
        '2026-03-06T20:29:53.447021291Z {"http.resp.took_ms":74}',
    ]
    samples = parse_k8s_log_lines(lines)
    assert len(samples) == 2
    assert samples[0].latency_ms == 29.0
    assert samples[1].latency_ms == 74.0


def test_k8s_log_parses_nanosecond_rfc3339_json_ts_field() -> None:
    lines = [
        '{"ts":"2026-03-06T20:29:52.347021290Z","http.resp.took_ms":315}',
    ]
    samples = parse_k8s_log_lines(lines)
    assert len(samples) == 1
    assert samples[0].latency_ms == 315.0
