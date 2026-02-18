import json
import os
import stat
import subprocess
from pathlib import Path


def test_internal_license_issue_and_verify(tmp_path: Path, mk_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    keygen = repo_root / "bin" / "mk-license-keygen"
    issue = repo_root / "bin" / "mk-license-issue"

    kid = "mk-internal-2026-02"
    private_path = tmp_path / "issuer.key"
    keyring_path = tmp_path / "license_public_keys.json"
    license_path = tmp_path / "license.json"
    verify_out = tmp_path / "verify_out"

    cp_keygen = subprocess.run(
        [str(keygen), "--kid", kid, "--out-priv", str(private_path), "--out-keyring", str(keyring_path)],
        text=True,
        capture_output=True,
    )
    assert cp_keygen.returncode == 0, cp_keygen.stderr
    assert cp_keygen.stderr == ""
    assert private_path.exists()
    assert keyring_path.exists()
    mode = stat.S_IMODE(private_path.stat().st_mode)
    assert mode == 0o600

    env = os.environ.copy()
    env["MODEKEEPER_ISSUER_PRIVKEY_PATH"] = str(private_path)
    cp_issue = subprocess.run(
        [
            str(issue),
            "--kid",
            kid,
            "--org",
            "Acme Internal",
            "--expires",
            "2100-01-01T00:00:00Z",
            "--entitlements",
            "apply,observe,paid",
            "--out",
            str(license_path),
        ],
        text=True,
        capture_output=True,
        env=env,
    )
    assert cp_issue.returncode == 0, cp_issue.stderr
    assert cp_issue.stderr == ""
    assert license_path.exists()

    verify_env = os.environ.copy()
    verify_env["MODEKEEPER_LICENSE_PUBLIC_KEYS_PATH"] = str(keyring_path)
    cp_verify = subprocess.run(
        [str(mk_path), "license", "verify", "--license", str(license_path), "--out", str(verify_out)],
        text=True,
        capture_output=True,
        env=verify_env,
    )
    assert cp_verify.returncode == 0, cp_verify.stderr

    report = json.loads((verify_out / "license_verify_latest.json").read_text(encoding="utf-8"))
    assert report["license_ok"] is True
    assert report["reason"] == "ok"
