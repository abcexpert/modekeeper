import base64
import json
import os
import re
import subprocess
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from modekeeper.license.canonical import canonical_json_bytes


def _run(mk: Path, args: list[str], *, cwd: Path | None = None, env: dict | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(mk), *args],
        text=True,
        capture_output=True,
        cwd=str(cwd) if cwd is not None else None,
        env=env,
    )


def _deterministic_private_key() -> Ed25519PrivateKey:
    return Ed25519PrivateKey.from_private_bytes(bytes(range(32)))


def _public_key_b64(private_key: Ed25519PrivateKey) -> str:
    raw = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return base64.b64encode(raw).decode("ascii")


def _sign_license(payload: dict) -> str:
    signature = _deterministic_private_key().sign(canonical_json_bytes(payload))
    return base64.b64encode(signature).decode("ascii")


def test_license_verify_defaults_home_config(tmp_path: Path, mk_path: Path) -> None:
    home_dir = tmp_path / "home"
    config_dir = home_dir / ".config" / "modekeeper"
    config_dir.mkdir(parents=True, exist_ok=True)

    payload = {
        "schema_version": "license.v1",
        "org": "Acme",
        "issued_at": 1700000000,
        "expires_at": 4102444800,
        "entitlements": ["observe", "apply"],
        "kid": "dev-kid",
    }
    license_data = {**payload, "signature": _sign_license(payload)}
    (config_dir / "license.json").write_text(
        json.dumps(license_data, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    (config_dir / "license_public_keys.json").write_text(
        json.dumps({"dev-kid": _public_key_b64(_deterministic_private_key())}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    out_dir = tmp_path / "out_verify"
    env = os.environ.copy()
    env["HOME"] = str(home_dir)
    env.pop("MODEKEEPER_LICENSE_PUBLIC_KEYS_PATH", None)
    cp = _run(mk_path, ["license", "verify", "--out", str(out_dir)], env=env)
    assert cp.returncode == 0, cp.stderr

    latest = out_dir / "license_verify_latest.json"
    assert latest.exists()
    report = json.loads(latest.read_text(encoding="utf-8"))
    assert report.get("license_ok") is True
    assert report.get("reason") == "ok"


def test_quickstart_defaults_out_dir(tmp_path: Path, mk_path: Path) -> None:
    cp = _run(mk_path, ["quickstart", "--observe-source", "synthetic"], cwd=tmp_path)
    assert cp.returncode == 0, cp.stderr

    report_dir = tmp_path / "report"
    created = [path for path in report_dir.glob("quickstart_*") if path.is_dir()]
    assert len(created) == 1
    assert re.fullmatch(r"quickstart_\d{8}T\d{6}Z", created[0].name)
    assert (created[0] / "summary.md").exists()
