import argparse
import json
from pathlib import Path

from modekeeper.cli import cmd_k8s_preflight


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_k8s_preflight_read_only_report_with_blocker(monkeypatch, tmp_path: Path, capsys) -> None:
    pods_stdout = "\n".join([f"pod-{i} 1/1 Running 0 1m node-a" for i in range(30)])

    responses = {
        ("config", "current-context"): {"rc": 0, "stdout": "kind-test\n", "stderr": "", "error": None},
        ("cluster-info",): {"rc": 0, "stdout": "Kubernetes control plane is running\n", "stderr": "", "error": None},
        ("get", "ns"): {"rc": 0, "stdout": "default\nkube-system\n", "stderr": "", "error": None},
        ("-n", "default", "get", "deploy", "trainer", "-o", "wide"): {
            "rc": 0,
            "stdout": "trainer 1/1 1 1 1m\n",
            "stderr": "",
            "error": None,
        },
        ("-n", "default", "get", "pods", "-o", "wide"): {
            "rc": 0,
            "stdout": pods_stdout,
            "stderr": "",
            "error": None,
        },
        ("auth", "can-i", "get", "pods", "-n", "default"): {"rc": 0, "stdout": "yes\n", "stderr": "", "error": None},
        ("auth", "can-i", "get", "deployments.apps", "-n", "default"): {
            "rc": 1,
            "stdout": "no\n",
            "stderr": "forbidden\n",
            "error": None,
        },
    }

    def fake_kubectl(args: list[str], timeout_s: float = 20.0) -> dict:
        del timeout_s
        return responses.get(tuple(args), {"rc": 1, "stdout": "", "stderr": "unexpected", "error": None})

    monkeypatch.setattr("modekeeper.cli._kubectl", fake_kubectl)

    out_dir = tmp_path / "out"
    args = argparse.Namespace(k8s_namespace="default", k8s_deployment="trainer", out=str(out_dir))
    rc = cmd_k8s_preflight(args)
    assert rc == 1

    latest = out_dir / "preflight_latest.json"
    summary = out_dir / "preflight_summary.md"
    explain = out_dir / "explain.jsonl"
    assert latest.exists()
    assert summary.exists()
    assert explain.exists()

    data = json.loads(latest.read_text(encoding="utf-8"))
    assert data["schema_version"] == "preflight.v0"
    assert data["ok"] is False
    assert data["top_blocker"] == "can_i_get_deployments_apps failed"
    assert data["k8s_context"] == "kind-test"
    assert data["k8s_namespace"] == "default"
    assert data["k8s_deployment"] == "trainer"
    assert len(data["checks"]) == 7

    pods_check = next(item for item in data["checks"] if item["name"] == "get_pods_wide")
    assert pods_check["ok"] is True
    assert "...(truncated)" in pods_check["stdout_snip"]

    artifact_paths = set(data["key_artifacts"])
    assert str(latest) in artifact_paths
    assert str(summary) in artifact_paths
    assert str(explain) in artifact_paths

    events = _read_jsonl(explain)
    names = [event.get("event") for event in events]
    assert "k8s_preflight_start" in names
    assert "k8s_preflight_report" in names

    printed = capsys.readouterr().out.strip()
    assert "ok=false" in printed
    assert "top_blocker=can_i_get_deployments_apps failed" in printed
    assert f"preflight={latest}" in printed
    assert f"summary={summary}" in printed


def test_k8s_preflight_gpu_visibility_notes(monkeypatch, tmp_path: Path, capsys) -> None:
    responses = {
        ("config", "current-context"): {"rc": 0, "stdout": "kind-test\n", "stderr": "", "error": None},
        ("cluster-info",): {"rc": 0, "stdout": "Kubernetes control plane is running\n", "stderr": "", "error": None},
        ("get", "ns"): {"rc": 0, "stdout": "default\nkube-system\n", "stderr": "", "error": None},
        ("-n", "default", "get", "deploy", "trainer", "-o", "wide"): {
            "rc": 0,
            "stdout": "trainer 1/1 1 1 1m\n",
            "stderr": "",
            "error": None,
        },
        ("-n", "default", "get", "pods", "-o", "wide"): {
            "rc": 0,
            "stdout": "trainer-abc 1/1 Running 0 1m node-a\n",
            "stderr": "",
            "error": None,
        },
        ("auth", "can-i", "get", "pods", "-n", "default"): {"rc": 0, "stdout": "yes\n", "stderr": "", "error": None},
        ("auth", "can-i", "get", "deployments.apps", "-n", "default"): {
            "rc": 0,
            "stdout": "yes\n",
            "stderr": "",
            "error": None,
        },
        ("get", "nodes", "-o", "json"): {
            "rc": 0,
            "stdout": json.dumps(
                {"items": [{"status": {"capacity": {"cpu": "16"}, "allocatable": {"cpu": "16"}}}]}
            ),
            "stderr": "",
            "error": None,
        },
        ("-n", "kube-system", "get", "ds", "-o", "name"): {
            "rc": 0,
            "stdout": "daemonset.apps/kube-proxy\n",
            "stderr": "",
            "error": None,
        },
        ("-n", "kube-system", "get", "pods", "-o", "name"): {
            "rc": 0,
            "stdout": "pod/coredns-123\n",
            "stderr": "",
            "error": None,
        },
        ("-n", "default", "get", "deploy", "trainer", "-o", "json"): {
            "rc": 0,
            "stdout": json.dumps(
                {
                    "spec": {
                        "template": {
                            "spec": {
                                "containers": [
                                    {
                                        "name": "trainer",
                                        "resources": {"limits": {"cpu": "1"}, "requests": {"memory": "1Gi"}},
                                    }
                                ]
                            }
                        }
                    }
                }
            ),
            "stderr": "",
            "error": None,
        },
    }

    def fake_kubectl(args: list[str], timeout_s: float = 20.0) -> dict:
        del timeout_s
        return responses.get(tuple(args), {"rc": 1, "stdout": "", "stderr": "unexpected", "error": None})

    monkeypatch.setattr("modekeeper.cli._kubectl", fake_kubectl)

    out_dir = tmp_path / "out"
    args = argparse.Namespace(k8s_namespace="default", k8s_deployment="trainer", out=str(out_dir))
    rc = cmd_k8s_preflight(args)
    assert rc == 0

    latest = out_dir / "preflight_latest.json"
    summary = out_dir / "preflight_summary.md"
    data = json.loads(latest.read_text(encoding="utf-8"))
    assert data["ok"] is True
    assert data["top_blocker"] is None
    assert data["gpu_capacity_present"] is False
    assert data["nvidia_device_plugin_present"] is False
    assert data["deploy_gpu_request"] == 0
    assert data["notes"] == [
        "gpu_not_in_cluster",
        "device_plugin_missing",
        "deploy_not_requesting_gpu",
    ]

    summary_text = summary.read_text(encoding="utf-8")
    assert "gpu_capacity_present: False" in summary_text
    assert "nvidia_device_plugin_present: False" in summary_text
    assert "deploy_gpu_request: 0" in summary_text
    assert 'notes: ["gpu_not_in_cluster","device_plugin_missing","deploy_not_requesting_gpu"]' in summary_text

    printed = capsys.readouterr().out.strip()
    assert "gpu_capacity_present=false" in printed
    assert "device_plugin_present=false" in printed
    assert "deploy_gpu_request=0" in printed
