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
