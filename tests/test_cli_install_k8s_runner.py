import subprocess
from pathlib import Path


def _run(mk: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(mk), *args],
        text=True,
        capture_output=True,
    )


def test_cli_install_k8s_runner_generates_expected_bundle(tmp_path: Path, mk_path: Path) -> None:
    out_dir = tmp_path / "out"
    cp = _run(mk_path, ["install", "k8s-runner", "--out", str(out_dir)])
    assert cp.returncode == 0, cp.stderr

    expected_files = (
        "00_namespace.yaml",
        "10_serviceaccount.yaml",
        "20_rbac.yaml",
        "30_job.yaml",
        "README.md",
        "apply.sh",
        "rollback.sh",
    )
    for name in expected_files:
        assert (out_dir / name).exists(), name

    namespace_yaml = (out_dir / "00_namespace.yaml").read_text(encoding="utf-8")
    serviceaccount_yaml = (out_dir / "10_serviceaccount.yaml").read_text(encoding="utf-8")
    rbac_yaml = (out_dir / "20_rbac.yaml").read_text(encoding="utf-8")
    job_yaml = (out_dir / "30_job.yaml").read_text(encoding="utf-8")
    apply_sh = (out_dir / "apply.sh").read_text(encoding="utf-8")
    rollback_sh = (out_dir / "rollback.sh").read_text(encoding="utf-8")

    assert "kind: Namespace" in namespace_yaml
    assert "kind: ServiceAccount" in serviceaccount_yaml
    assert "kind: ClusterRole" in rbac_yaml
    assert "kind: ClusterRoleBinding" in rbac_yaml
    assert "kind: Job" in job_yaml
    assert "mk quickstart --out /out/quickstart" in job_yaml
    assert "sleep 900" in job_yaml
    assert "MODEKEEPER_DONE" in job_yaml


    assert "set -Eeuo pipefail" in apply_sh
    assert "kubectl apply -f 00_namespace.yaml" in apply_sh
    assert "kubectl apply -f 10_serviceaccount.yaml" in apply_sh
    assert "kubectl apply -f 20_rbac.yaml" in apply_sh
    assert "kubectl apply -f 30_job.yaml" in apply_sh

    assert "set -Eeuo pipefail" in rollback_sh
    assert "kubectl delete -f 30_job.yaml" in rollback_sh
    assert "kubectl delete -f 20_rbac.yaml" in rollback_sh
    assert "kubectl delete -f 10_serviceaccount.yaml" in rollback_sh
    assert "kubectl delete -f 00_namespace.yaml" in rollback_sh
