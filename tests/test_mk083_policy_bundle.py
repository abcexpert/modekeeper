import json
import subprocess
from pathlib import Path


def _run(mk: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run([str(mk), *args], text=True, capture_output=True)


def _write_plan(plan_path: Path) -> None:
    plan_path.write_text(
        json.dumps(
            [
                {
                    "namespace": "default",
                    "name": "trainer",
                    "patch": {"spec": {"replicas": 2}},
                }
            ]
        ),
        encoding="utf-8",
    )


def _assert_bundle_shape(bundle: dict) -> None:
    required_top = {
        "schema_version",
        "bundle_version",
        "created_at",
        "mk_version",
        "provenance",
        "policy",
        "inputs",
        "rollback",
    }
    assert required_top.issubset(set(bundle.keys()))
    assert bundle.get("schema_version") == "policy_bundle.v1"
    assert bundle.get("bundle_version") == 1
    assert isinstance(bundle.get("created_at"), int)
    policy = bundle.get("policy")
    assert isinstance(policy, dict)
    assert isinstance(policy.get("id"), str)
    assert policy.get("id")


def test_mk083_closed_loop_emits_policy_bundle(tmp_path: Path, mk_path: Path) -> None:
    out_dir = tmp_path / "out"
    cp = _run(mk_path, ["closed-loop", "run", "--dry-run", "--out", str(out_dir)])
    assert cp.returncode == 0

    bundle_path = out_dir / "policy_bundle_latest.json"
    assert bundle_path.exists()
    bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
    _assert_bundle_shape(bundle)


def test_mk083_closed_loop_apply_emits_rollback_skeleton_when_verify_exists(
    tmp_path: Path,
    mk_path: Path,
) -> None:
    out_dir = tmp_path / "out"
    cp = _run(mk_path, ["closed-loop", "run", "--apply", "--out", str(out_dir)])
    assert cp.returncode == 2
    assert cp.stderr.strip() == "PRO REQUIRED: closed-loop --apply"
    assert (out_dir / "k8s_apply_latest.json").exists()
    apply_report = json.loads((out_dir / "k8s_apply_latest.json").read_text(encoding="utf-8"))
    assert apply_report.get("block_reason") == "pro_required"
    assert apply_report.get("reason") == "pro_required"

    bundle = json.loads((out_dir / "policy_bundle_latest.json").read_text(encoding="utf-8"))
    _assert_bundle_shape(bundle)


def test_mk083_k8s_apply_blocked_still_emits_policy_bundle(tmp_path: Path, mk_path: Path) -> None:
    plan_path = tmp_path / "plan.json"
    _write_plan(plan_path)
    out_dir = tmp_path / "out"

    cp = _run(mk_path, ["k8s", "apply", "--plan", str(plan_path), "--out", str(out_dir)])
    assert cp.returncode == 2
    assert (out_dir / "k8s_apply_latest.json").exists()

    bundle_path = out_dir / "policy_bundle_latest.json"
    assert bundle_path.exists()
    bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
    _assert_bundle_shape(bundle)
