import json
import os
import subprocess
from pathlib import Path


def test_k8s_render_writes_kubectl_plan(tmp_path: Path, mk_path: Path) -> None:
    plan = [
        {
            "namespace": "ns1",
            "name": "dep1",
            "patch": {
                "metadata": {
                    "annotations": {
                        "modekeeper/knob.grad_accum_steps": "4",
                    }
                },
                "spec": {
                    "template": {
                        "metadata": {
                            "annotations": {
                                "modekeeper/knob.grad_accum_steps": "4",
                            }
                        }
                    }
                },
            },
        },
        {
            "namespace": "ns1",
            "name": "dep1",
            "patch": {
                "metadata": {
                    "annotations": {
                        "modekeeper/knob.microbatch_size": "32",
                    }
                },
                "spec": {
                    "template": {
                        "metadata": {
                            "annotations": {
                                "modekeeper/knob.microbatch_size": "32",
                            }
                        }
                    }
                },
            },
        },
    ]
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(json.dumps(plan, indent=2), encoding="utf-8")

    out_dir = tmp_path / "out"
    mk = mk_path
    subprocess.run(
        [str(mk), "k8s", "render", "--plan", str(plan_path), "--out", str(out_dir)],
        check=True,
        capture_output=True,
        text=True,
    )

    kubectl_path = out_dir / "k8s_plan.kubectl.sh"
    assert kubectl_path.exists()
    assert os.access(kubectl_path, os.X_OK)
    script_text = kubectl_path.read_text(encoding="utf-8")
    assert script_text.startswith("#!/usr/bin/env bash")
    assert "Target: namespace=ns1 deployment=dep1" in script_text
    assert "kubectl -n ns1 patch deployment/dep1 --type merge -p" in script_text

    explain_path = out_dir / "explain.jsonl"
    assert explain_path.exists()
    explain_events = [
        json.loads(line).get("event")
        for line in explain_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert "k8s_render_start" in explain_events
    assert "k8s_kubectl_plan_written" in explain_events

    latest_path = out_dir / "k8s_render_latest.json"
    assert latest_path.exists()
    latest = json.loads(latest_path.read_text(encoding="utf-8"))
    assert latest.get("k8s_plan_items") == 2
    assert latest.get("k8s_namespace") == "ns1"
    assert latest.get("k8s_deployment") == "dep1"
    latest_kubectl_path = latest.get("k8s_kubectl_plan_path")
    assert latest_kubectl_path
    assert Path(latest_kubectl_path).exists()


def test_k8s_render_escapes_single_quotes_in_patch_json(tmp_path: Path, mk_path: Path) -> None:
    plan = [
        {
            "namespace": "ns1",
            "name": "dep1",
            "patch": {
                "metadata": {
                    "annotations": {
                        "modekeeper/note": "O'Reilly",
                    }
                }
            },
        }
    ]
    plan_path = tmp_path / "plan.json"
    plan_path.write_text(
        json.dumps(plan, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    out_dir = tmp_path / "out"
    mk = mk_path
    subprocess.run(
        [str(mk), "k8s", "render", "--plan", str(plan_path), "--out", str(out_dir)],
        check=True,
        capture_output=True,
        text=True,
    )

    script_text = (out_dir / "k8s_plan.kubectl.sh").read_text(encoding="utf-8")
    # bash-safe single-quote escaping inside single-quoted JSON: ' -> '\'' (so we expect O'\''Reilly)
    assert "O'\\''Reilly" in script_text


def test_k8s_render_empty_plan_writes_kubectl_free_script(tmp_path: Path, mk_path: Path) -> None:
    plan_path = tmp_path / "plan.json"
    plan_path.write_text("[]\n", encoding="utf-8")

    out_dir = tmp_path / "out"
    mk = mk_path
    subprocess.run(
        [str(mk), "k8s", "render", "--plan", str(plan_path), "--out", str(out_dir)],
        check=True,
        capture_output=True,
        text=True,
    )

    kubectl_path = out_dir / "k8s_plan.kubectl.sh"
    assert kubectl_path.exists()
    assert os.access(kubectl_path, os.X_OK)
    script_text = kubectl_path.read_text(encoding="utf-8")
    assert "kubectl" not in script_text
