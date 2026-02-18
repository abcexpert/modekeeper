import json
import os
import subprocess
import sys
from pathlib import Path

from modekeeper.license.verify import verify_license


def test_mk_mint_dev_license_kube_independent(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    script = repo_root / "bin" / "mk-mint-dev-license"
    stdout_path = tmp_path / "license_stdout.json"

    # Force a no-kubectl/minikube environment to validate kube-independent minting.
    empty_bin = tmp_path / "empty-bin"
    empty_bin.mkdir()
    env = os.environ.copy()
    env["PATH"] = str(empty_bin)
    env["HOME"] = str(tmp_path)

    cp = subprocess.run(
        [sys.executable, str(script)],
        cwd=str(repo_root),
        text=True,
        capture_output=True,
        env=env,
    )
    assert cp.returncode == 0, cp.stderr
    assert cp.stderr == ""

    stdout_path.write_text(cp.stdout, encoding="utf-8")
    minted = json.loads(stdout_path.read_text(encoding="utf-8"))
    assert isinstance(minted, dict)
    kid = minted.get("kid")
    assert isinstance(kid, str) and kid

    keys_path = tmp_path / ".config" / "modekeeper" / "license_public_keys.json"
    assert keys_path.exists()
    key_map = json.loads(keys_path.read_text(encoding="utf-8"))
    assert isinstance(key_map, dict)
    assert kid in key_map

    license_path = tmp_path / "license.json"
    license_path.write_text(
        json.dumps(minted, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    old_keys_path = os.environ.get("MODEKEEPER_LICENSE_PUBLIC_KEYS_PATH")
    os.environ["MODEKEEPER_LICENSE_PUBLIC_KEYS_PATH"] = str(keys_path)
    try:
        report = verify_license(license_path)
    finally:
        if old_keys_path is None:
            os.environ.pop("MODEKEEPER_LICENSE_PUBLIC_KEYS_PATH", None)
        else:
            os.environ["MODEKEEPER_LICENSE_PUBLIC_KEYS_PATH"] = old_keys_path
    assert report.get("license_ok") is True, report
