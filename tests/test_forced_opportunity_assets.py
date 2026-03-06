import subprocess
from pathlib import Path


ROOT = Path("examples/online-boutique/forced-opportunity")


def test_forced_opportunity_assets_exist() -> None:
    assert (ROOT / "README.md").exists()
    assert (ROOT / "manifests/oversized-requests-productcatalogservice.yaml").exists()
    assert (ROOT / "manifests/replica-overprovisioning-emailservice.yaml").exists()
    assert (ROOT / "manifests/burst-traffic-loadgenerator-job.yaml").exists()


def test_scenario_manifest_helper_is_deterministic() -> None:
    script = ROOT / "scripts/scenario_manifest.sh"

    def _run(name: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(["bash", str(script), name], text=True, capture_output=True, check=False)

    cp = _run("oversized_requests")
    assert cp.returncode == 0
    assert cp.stdout.strip() == "manifests/oversized-requests-productcatalogservice.yaml"

    cp = _run("replica_overprovisioning")
    assert cp.returncode == 0
    assert cp.stdout.strip() == "manifests/replica-overprovisioning-emailservice.yaml"

    cp = _run("burst_traffic")
    assert cp.returncode == 0
    assert cp.stdout.strip() == "manifests/burst-traffic-loadgenerator-job.yaml"

    cp = _run("unknown")
    assert cp.returncode != 0
    assert "unknown scenario" in cp.stderr


def test_forced_opportunity_manifests_do_not_pin_namespace() -> None:
    manifest_paths = [
        ROOT / "manifests/oversized-requests-productcatalogservice.yaml",
        ROOT / "manifests/replica-overprovisioning-emailservice.yaml",
        ROOT / "manifests/burst-traffic-loadgenerator-job.yaml",
    ]
    for manifest_path in manifest_paths:
        text = manifest_path.read_text(encoding="utf-8")
        assert "namespace:" not in text


def test_forced_opportunity_helpers_use_namespace_and_k8s_logs() -> None:
    apply_script = (ROOT / "scripts/apply_scenario.sh").read_text(encoding="utf-8")
    assert 'kubectl -n "$NAMESPACE" patch deployment "$deployment" --type=strategic --patch-file "$MANIFEST_PATH"' in apply_script
    assert 'kubectl -n "$NAMESPACE" patch deployment "${DEPLOYMENT:-frontend}" --type=strategic --patch "' in apply_script
    assert 'kubectl -n "$NAMESPACE" patch deployment "${DEPLOYMENT:-emailservice}" --type=strategic --patch "' in apply_script
    assert 'kubectl -n "$NAMESPACE" apply -f "$MANIFEST_PATH"' in apply_script
    assert 'kubectl -n "$NAMESPACE" delete -f "$MANIFEST_PATH" --ignore-not-found=true' in apply_script

    assess_script = (ROOT / "scripts/run_readonly_assessment.sh").read_text(encoding="utf-8")
    assert "mk eval k8s" not in assess_script
    assert "mk observe \\" in assess_script
    assert "--source k8s-logs" in assess_script
    assert assess_script.count("--observe-source k8s-logs") == 2


def test_oversized_requests_manifest_targets_frontend() -> None:
    manifest = (ROOT / "manifests/oversized-requests-productcatalogservice.yaml").read_text(encoding="utf-8")
    assert "name: frontend" in manifest
