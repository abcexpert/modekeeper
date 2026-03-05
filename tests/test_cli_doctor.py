import os
import json
import subprocess
from pathlib import Path


def _run(mk: Path, env: dict[str, str], out_dir: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(mk), "doctor", "--out", str(out_dir)],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )


def test_doctor_pass_with_fake_kubectl_and_kubeconfig(tmp_path: Path, mk_path: Path) -> None:
    kubectl = tmp_path / "kubectl"
    kubectl.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    kubectl.chmod(0o755)

    kubeconfig = tmp_path / "kubeconfig"
    kubeconfig.write_text("apiVersion: v1\n", encoding="utf-8")

    env = {
        **os.environ,
        "KUBECTL": str(kubectl),
        "KUBECONFIG": str(kubeconfig),
    }
    out_dir = tmp_path / "out"
    cp = _run(mk_path, env, out_dir)
    assert cp.returncode == 0
    assert "Doctor result: PASS" in cp.stdout
    assert (out_dir / "doctor_latest.json").exists()
    assert (out_dir / "summary.md").exists()
    ts_reports = list(out_dir.glob("doctor_*.json"))
    assert len(ts_reports) == 2
    latest_payload = json.loads((out_dir / "doctor_latest.json").read_text(encoding="utf-8"))
    assert latest_payload["ok"] is True


def test_doctor_fails_with_missing_kubeconfig(tmp_path: Path, mk_path: Path) -> None:
    kubectl = tmp_path / "kubectl"
    kubectl.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    kubectl.chmod(0o755)

    missing_kubeconfig = tmp_path / "missing-kubeconfig"
    env = {
        **os.environ,
        "KUBECTL": str(kubectl),
        "KUBECONFIG": str(missing_kubeconfig),
    }
    out_dir = tmp_path / "out"
    cp = _run(mk_path, env, out_dir)
    assert cp.returncode == 2
    assert "Doctor result: FAIL" in cp.stdout
    assert (out_dir / "doctor_latest.json").exists()
    assert (out_dir / "summary.md").exists()
    ts_reports = list(out_dir.glob("doctor_*.json"))
    assert len(ts_reports) == 2
    latest_payload = json.loads((out_dir / "doctor_latest.json").read_text(encoding="utf-8"))
    assert latest_payload["ok"] is False
