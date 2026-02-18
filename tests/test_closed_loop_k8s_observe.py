import json
import os
import subprocess
from pathlib import Path


def _write_fake_kubectl(path: Path, log_output: str) -> None:
    script = f"""#!/usr/bin/env bash
set -Eeuo pipefail

if [[ "$1" == "logs" ]]; then
  cat <<'EOF'
{log_output}
EOF
  exit 0
fi

echo "unexpected args: $*" >&2
exit 1
"""
    path.write_text(script, encoding="utf-8")
    path.chmod(0o755)


def _write_fake_kubectl_for_drift_annotations(
    path: Path,
    *,
    namespace: str,
    deployment: str,
    grad_accum_steps: int,
    microbatch_size: int,
) -> None:
    deploy_json = json.dumps(
        {
            "spec": {
                "template": {
                    "metadata": {
                        "annotations": {
                            "modekeeper/knob.grad_accum_steps": str(grad_accum_steps),
                            "modekeeper/knob.microbatch_size": str(microbatch_size),
                        }
                    }
                }
            }
        }
    )
    script = f"""#!/usr/bin/env bash
set -Eeuo pipefail

if [[ $# -ge 6 && "$1" == "-n" && "$2" == "{namespace}" && "$3" == "get" && "$4" == "deployment/{deployment}" && "$5" == "-o" && "$6" == "json" ]]; then
  cat <<'EOF'
{deploy_json}
EOF
  exit 0
fi

echo "unexpected args: $*" >&2
exit 1
"""
    path.write_text(script, encoding="utf-8")
    path.chmod(0o755)


def _explain_event_payloads(path: Path, event_name: str) -> list[dict]:
    payloads: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        record = json.loads(line)
        if record.get("event") == event_name:
            payload = record.get("payload")
            if isinstance(payload, dict):
                payloads.append(payload)
    return payloads


def test_closed_loop_run_k8s_observe(tmp_path: Path, mk_path: Path) -> None:
    kubectl = tmp_path / "kubectl"
    log_output = "\n".join(
        [
            '{"ts":"2026-01-01T00:00:00Z","step_time_ms":120,"loss":1.0}',
            '{"ts":"2026-01-01T00:00:01Z","step_time_ms":130}',
        ]
    )
    _write_fake_kubectl(kubectl, log_output)

    out_dir = tmp_path / "closed_loop_out"
    env = {**os.environ, "KUBECTL": str(kubectl)}
    subprocess.run(
        [
            str(mk_path),
            "closed-loop",
            "run",
            "--scenario",
            "drift",
            "--observe-source",
            "k8s",
            "--observe-duration",
            "10s",
            "--observe-container",
            "trainer",
            "--k8s-namespace",
            "ns1",
            "--k8s-deployment",
            "dep1",
            "--dry-run",
            "--out",
            str(out_dir),
        ],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )

    latest = json.loads((out_dir / "closed_loop_latest.json").read_text(encoding="utf-8"))
    assert latest.get("proposed") == []


def test_closed_loop_run_drift_k8s_mode_equal_targets_no_actions(tmp_path: Path, mk_path: Path) -> None:
    kubectl = tmp_path / "kubectl"
    _write_fake_kubectl_for_drift_annotations(
        kubectl,
        namespace="ns1",
        deployment="dep1",
        grad_accum_steps=8,
        microbatch_size=32,
    )
    out_dir = tmp_path / "closed_loop_out"
    env = {**os.environ, "KUBECTL": str(kubectl)}
    subprocess.run(
        [
            str(mk_path),
            "closed-loop",
            "run",
            "--scenario",
            "drift",
            "--dry-run",
            "--k8s-namespace",
            "ns1",
            "--k8s-deployment",
            "dep1",
            "--out",
            str(out_dir),
        ],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    latest = json.loads((out_dir / "closed_loop_latest.json").read_text(encoding="utf-8"))
    assert latest.get("signals", {}).get("drift") is False
    assert latest.get("proposed") == []
    assert latest.get("k8s_plan_items") == 0

    explain_path = out_dir / "explain.jsonl"
    observe_payloads = _explain_event_payloads(explain_path, "closed_loop_observe_source")
    assert observe_payloads
    assert observe_payloads[-1].get("source") == "k8s"
    drift_payloads = _explain_event_payloads(explain_path, "closed_loop_drift_observed_knobs")
    assert drift_payloads
    assert drift_payloads[-1].get("k8s_drift_triggered") is False


def test_closed_loop_run_drift_k8s_mode_coalesces_patch(tmp_path: Path, mk_path: Path) -> None:
    kubectl = tmp_path / "kubectl"
    _write_fake_kubectl_for_drift_annotations(
        kubectl,
        namespace="ns1",
        deployment="dep1",
        grad_accum_steps=4,
        microbatch_size=16,
    )
    out_dir = tmp_path / "closed_loop_out"
    env = {**os.environ, "KUBECTL": str(kubectl)}
    subprocess.run(
        [
            str(mk_path),
            "closed-loop",
            "run",
            "--scenario",
            "drift",
            "--dry-run",
            "--k8s-namespace",
            "ns1",
            "--k8s-deployment",
            "dep1",
            "--out",
            str(out_dir),
        ],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )

    latest = json.loads((out_dir / "closed_loop_latest.json").read_text(encoding="utf-8"))
    assert latest.get("signals", {}).get("drift") is True
    assert latest.get("k8s_plan_items") == 1

    plan = json.loads((out_dir / "k8s_plan.json").read_text(encoding="utf-8"))
    assert isinstance(plan, list)
    assert len(plan) == 1
    annotations = (
        plan[0]
        .get("patch", {})
        .get("spec", {})
        .get("template", {})
        .get("metadata", {})
        .get("annotations", {})
    )
    assert annotations.get("modekeeper/knob.grad_accum_steps") == "8"
    assert annotations.get("modekeeper/knob.microbatch_size") == "32"

    script_text = (out_dir / "k8s_plan.kubectl.sh").read_text(encoding="utf-8")
    assert script_text.count("kubectl -n ns1 patch deployment/dep1 --type merge -p") == 1
    assert "modekeeper/knob.grad_accum_steps" in script_text
    assert "modekeeper/knob.microbatch_size" in script_text

    explain_path = out_dir / "explain.jsonl"
    observe_payloads = _explain_event_payloads(explain_path, "closed_loop_observe_source")
    assert observe_payloads
    assert observe_payloads[-1].get("source") == "k8s"
    drift_payloads = _explain_event_payloads(explain_path, "closed_loop_drift_observed_knobs")
    assert drift_payloads
    assert drift_payloads[-1].get("k8s_drift_triggered") is True


def test_closed_loop_run_drift_k8s_mode_falls_back_to_synthetic_without_kubectl_env(
    tmp_path: Path, mk_path: Path
) -> None:
    out_dir = tmp_path / "closed_loop_out"
    env = dict(os.environ)
    env.pop("KUBECTL", None)
    subprocess.run(
        [
            str(mk_path),
            "closed-loop",
            "run",
            "--scenario",
            "drift",
            "--dry-run",
            "--k8s-namespace",
            "ns1",
            "--k8s-deployment",
            "dep1",
            "--out",
            str(out_dir),
        ],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )

    latest = json.loads((out_dir / "closed_loop_latest.json").read_text(encoding="utf-8"))
    knobs = {item.get("knob") for item in (latest.get("proposed") or [])}
    assert "grad_accum_steps" in knobs
    assert "microbatch_size" in knobs

    explain_path = out_dir / "explain.jsonl"
    observe_payloads = _explain_event_payloads(explain_path, "closed_loop_observe_source")
    assert observe_payloads
    assert observe_payloads[-1].get("source") == "synthetic"
