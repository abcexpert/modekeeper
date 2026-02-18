import json
import os
import subprocess
from pathlib import Path



EXPECTED_SCHEMA_BY_FILENAME = {
    "policy_bundle_latest.json": "policy_bundle.v1",
    "rollback_plan_latest.json": "rollback_plan.v1",
    "chords_validate_latest.json": "chords_validate.v0",
}

def _run(mk: Path, args: list[str], env: dict | None = None) -> subprocess.CompletedProcess[str]:
    e = os.environ.copy()
    if env:
        e.update(env)
    return subprocess.run([str(mk), *args], text=True, capture_output=True, env=e)


def test_reports_use_v0_contract(mk_path: Path, tmp_path: Path) -> None:
    observe_out = tmp_path / "observe"
    demo_out = tmp_path / "demo"
    cl_out = tmp_path / "closed_loop"
    render_out = tmp_path / "k8s_render"
    verify_out = tmp_path / "k8s_verify"
    apply_out = tmp_path / "k8s_apply"

    cp = _run(mk_path, ["observe", "--duration", "250ms", "--out", str(observe_out)])
    assert cp.returncode == 0

    cp = _run(mk_path, ["demo", "run", "--scenario", "drift", "--out", str(demo_out)])
    assert cp.returncode == 0

    cp = _run(
        mk_path,
        ["closed-loop", "run", "--scenario", "drift", "--dry-run", "--out", str(cl_out)],
    )
    assert cp.returncode == 0

    plan_path = cl_out / "k8s_plan.json"
    assert plan_path.exists()

    cp = _run(
        mk_path,
        ["k8s", "render", "--plan", str(plan_path), "--out", str(render_out)],
    )
    assert cp.returncode == 0

    cp = _run(
        mk_path,
        ["k8s", "verify", "--plan", str(plan_path), "--out", str(verify_out)],
    )
    assert cp.returncode == 0
    verify_latest = json.loads((verify_out / "k8s_verify_latest.json").read_text(encoding="utf-8"))
    verify_latest["ok"] = True
    (plan_path.parent / "k8s_verify_latest.json").write_text(
        json.dumps(verify_latest) + "\n",
        encoding="utf-8",
    )

    cp = _run(
        mk_path,
        ["k8s", "apply", "--plan", str(plan_path), "--out", str(apply_out)],
        env={
            "MODEKEEPER_PAID": "1",
            "MODEKEEPER_INTERNAL_OVERRIDE": "1",
            "HOME": str(tmp_path),
            "KUBECONFIG": str(tmp_path / "no-kubeconfig"),
        },
    )
    assert cp.returncode == 2

    out_dirs = [observe_out, demo_out, cl_out, render_out, verify_out, apply_out]
    prefixes = ["observe", "demo", "closed_loop", "k8s_render", "k8s_verify", "k8s_apply"]
    reports: list[Path] = []
    for out_dir in out_dirs:
        reports.extend(sorted(out_dir.glob("*_latest.json")))
        for prefix in prefixes:
            reports.extend(sorted(out_dir.glob(f"{prefix}_*.json")))

    assert reports, "expected report artifacts"

    for report_path in reports:
        data = json.loads(report_path.read_text(encoding="utf-8"))
        expected = EXPECTED_SCHEMA_BY_FILENAME.get(report_path.name)
        if expected is None:
            expected = "v0"
        assert data.get("schema_version") == expected
        if expected != "v0":
            continue
        duration = data.get("duration_s")
        assert isinstance(duration, int)
        assert duration >= 0
