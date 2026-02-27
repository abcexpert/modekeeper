from types import SimpleNamespace

from modekeeper.telemetry.k8s_log_source import K8sLogSource


def test_k8s_log_source_container_auto_omits_dash_c(monkeypatch) -> None:
    seen = {}

    def fake_run(argv, capture_output, text, timeout):
        seen["argv"] = argv
        return SimpleNamespace(returncode=0, stdout='{"ts": 1700000000000, "step_time_ms": 10}\n', stderr="")

    import modekeeper.telemetry.k8s_log_source as m

    monkeypatch.setattr(m.subprocess, "run", fake_run)

    src = K8sLogSource(
        namespace="default",
        deployment="trainer",
        container="auto",
        duration_ms=1000,
    )
    _ = src.read()

    argv = seen["argv"]
    assert "-c" not in argv


def test_k8s_log_source_container_explicit_includes_dash_c(monkeypatch) -> None:
    seen = {}

    def fake_run(argv, capture_output, text, timeout):
        seen["argv"] = argv
        return SimpleNamespace(returncode=0, stdout='{"ts": 1700000000000, "step_time_ms": 10}\n', stderr="")

    import modekeeper.telemetry.k8s_log_source as m

    monkeypatch.setattr(m.subprocess, "run", fake_run)

    src = K8sLogSource(
        namespace="default",
        deployment="trainer",
        container="nginx",
        duration_ms=1000,
    )
    _ = src.read()

    argv = seen["argv"]
    assert "-c" in argv
    assert argv[argv.index("-c") + 1] == "nginx"


def test_k8s_log_source_explicit_pod_targets_named_pod(monkeypatch) -> None:
    seen = {}

    def fake_run(argv, capture_output, text, timeout):
        seen["argv"] = argv
        return SimpleNamespace(returncode=0, stdout='{"ts": 1700000000000, "step_time_ms": 10}\n', stderr="")

    import modekeeper.telemetry.k8s_log_source as m

    monkeypatch.setattr(m.subprocess, "run", fake_run)

    src = K8sLogSource(
        namespace="default",
        deployment="trainer",
        container="trainer",
        duration_ms=1000,
        k8s_pod="trainer-7f44f44b8f-abcd1",
    )
    _ = src.read()

    argv = seen["argv"]
    assert argv[1] == "logs"
    assert "trainer-7f44f44b8f-abcd1" in argv
    assert "deployment/trainer" not in argv
    assert "-c" in argv
    assert argv[argv.index("-c") + 1] == "trainer"
