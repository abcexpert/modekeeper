import json
from types import SimpleNamespace

from modekeeper.cli import _build_telemetry_payload
from modekeeper.core.analysis import analyze_signals
from modekeeper.telemetry.k8s_log_source import K8sLogSource


def test_mk098_k8s_stdout_jsonl_ingests_loss_and_throughput(monkeypatch) -> None:
    pod_payload = {
        "items": [
            {
                "metadata": {
                    "name": "trainer-abc",
                    "annotations": {"modekeeper/telemetry": "stdout-jsonl"},
                },
                "spec": {"nodeName": "node-a"},
            }
        ]
    }
    log_rows = [
        {"ts": "2026-02-14T12:00:00Z", "step": 0, "loss": 1.25, "throughput": 120.0},
        {"ts": "2026-02-14T12:00:01Z", "step": 1, "loss": 1.16, "throughput": 121.0},
        {"ts": "2026-02-14T12:00:02Z", "step": 2, "loss": 1.08, "throughput": 123.0},
    ]

    def fake_run(argv, capture_output, text, timeout):
        if argv[1:3] == ["get", "pods"]:
            return SimpleNamespace(
                returncode=0,
                stdout=json.dumps(pod_payload),
                stderr="",
            )
        if argv[1] == "logs":
            return SimpleNamespace(
                returncode=0,
                stdout="\n".join(json.dumps(row, separators=(",", ":")) for row in log_rows) + "\n",
                stderr="",
            )
        return SimpleNamespace(returncode=1, stdout="", stderr="unexpected args")

    import modekeeper.telemetry.k8s_log_source as k8s_mod

    monkeypatch.setattr(k8s_mod.subprocess, "run", fake_run)

    source = K8sLogSource(
        namespace="default",
        deployment="trainer",
        container="trainer",
        duration_ms=5000,
    )
    samples = source.read()

    points = _build_telemetry_payload(samples).get("points")
    assert isinstance(points, list)
    assert len(points) == 3
    assert all(isinstance(point.get("throughput"), float) and point["throughput"] > 0 for point in points)
    assert all(isinstance(point.get("step"), int) for point in points)

    signals = analyze_signals(samples)
    assert "loss_missing" not in signals.get("notes", [])
