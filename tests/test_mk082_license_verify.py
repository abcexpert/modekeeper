import base64
import json
import os
import subprocess
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from modekeeper.license.canonical import canonical_json_bytes


def _run(mk: Path, args: list[str], env: dict | None = None) -> subprocess.CompletedProcess[str]:
    merged_env = None
    if env is not None:
        import os

        merged_env = os.environ.copy()
        merged_env.update(env)
    return subprocess.run([str(mk), *args], text=True, capture_output=True, env=merged_env)


def _deterministic_private_key() -> Ed25519PrivateKey:
    seed = bytes(range(32))
    return Ed25519PrivateKey.from_private_bytes(seed)


def _public_key_b64(private_key: Ed25519PrivateKey) -> str:
    raw = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return base64.b64encode(raw).decode("ascii")


def _sign_license(payload: dict) -> str:
    private_key = _deterministic_private_key()
    signature = private_key.sign(canonical_json_bytes(payload))
    return base64.b64encode(signature).decode("ascii")


def test_license_verify_cli_ok(tmp_path: Path, mk_path: Path) -> None:
    private_key = _deterministic_private_key()
    assert _public_key_b64(private_key) == "A6EHv/POEL4dcN0Y50vAmWfk1jCbpQ1fHdyGZBJVMbg="

    payload = {
        "schema_version": "license.v1",
        "org": "Acme",
        "issued_at": 1700000000,
        "expires_at": 4102444800,
        "entitlements": ["observe", "apply"],
    }
    license_data = {**payload, "signature": _sign_license(payload)}
    license_path = tmp_path / "license.json"
    license_path.write_text(
        json.dumps(license_data, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    out_dir = tmp_path / "out"
    home_dir = tmp_path / "home"
    home_dir.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env["HOME"] = str(home_dir)
    env.pop("MODEKEEPER_LICENSE_PUBLIC_KEYS_PATH", None)
    env.pop("MODEKEEPER_LICENSE_PATH", None)

    cp = _run(
        mk_path,
        ["license", "verify", "--license", str(license_path), "--out", str(out_dir)],
        env=env,
    )
    assert cp.returncode == 0

    latest = out_dir / "license_verify_latest.json"
    assert latest.exists()
    report = json.loads(latest.read_text(encoding="utf-8"))
    assert report.get("schema_version") == "license_verify.v0"
    assert report.get("license_ok") is True
    assert report.get("reason") == "ok"
    assert report.get("reason_code") == "ok"
    assert report.get("failure_code") is None
    assert report.get("kid") is None
    assert report.get("issuer") is None
    assert report.get("expires_at") == 4102444800
    assert report.get("expiry") == 4102444800
    assert report.get("entitlements_summary") == ["apply", "observe"]
    assert report.get("entitlements") == ["apply", "observe"]


def test_license_verify_cli_invalid_signature(tmp_path: Path, mk_path: Path) -> None:
    payload = {
        "schema_version": "license.v1",
        "org": "Acme",
        "issued_at": 1700000000,
        "expires_at": 4102444800,
        "entitlements": ["apply"],
    }
    license_data = {**payload, "signature": _sign_license(payload)}
    license_data["org"] = "Tampered"
    license_path = tmp_path / "license_bad.json"
    license_path.write_text(
        json.dumps(license_data, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    out_dir = tmp_path / "out_bad"
    cp = _run(mk_path, ["license", "verify", "--license", str(license_path), "--out", str(out_dir)])
    assert cp.returncode == 2

    latest = out_dir / "license_verify_latest.json"
    assert latest.exists()
    report = json.loads(latest.read_text(encoding="utf-8"))
    assert report.get("schema_version") == "license_verify.v0"
    assert report.get("license_ok") is False
    assert report.get("reason") == "license_invalid"
    assert report.get("reason_code") == "license_invalid"
    assert report.get("failure_code") == "license_signature_invalid"


def test_license_verify_cli_expired(tmp_path: Path, mk_path: Path) -> None:
    payload = {
        "schema_version": "license.v1",
        "org": "Acme",
        "issued_at": 1700000000,
        "expires_at": 1700000001,
        "entitlements": ["apply"],
    }
    license_data = {**payload, "signature": _sign_license(payload)}
    license_path = tmp_path / "license_expired.json"
    license_path.write_text(
        json.dumps(license_data, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    out_dir = tmp_path / "out_expired"
    cp = _run(mk_path, ["license", "verify", "--license", str(license_path), "--out", str(out_dir)])
    assert cp.returncode == 2

    report = json.loads((out_dir / "license_verify_latest.json").read_text(encoding="utf-8"))
    assert report.get("license_ok") is False
    assert report.get("reason") == "license_expired"
    assert report.get("reason_code") == "license_expired"
    assert report.get("failure_code") == "license_expired"


def test_license_verify_cli_defaults_home_config_zero_env(tmp_path: Path, mk_path: Path) -> None:
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

    out_dir = tmp_path / "out_default_verify"
    env = os.environ.copy()
    env["HOME"] = str(home_dir)
    env.pop("MODEKEEPER_LICENSE_PATH", None)
    env.pop("MODEKEEPER_LICENSE_PUBLIC_KEYS_PATH", None)
    cp = _run(mk_path, ["license", "verify", "--out", str(out_dir)], env=env)
    assert cp.returncode == 0, cp.stderr

    latest = out_dir / "license_verify_latest.json"
    assert latest.exists()
    report = json.loads(latest.read_text(encoding="utf-8"))
    assert report.get("license_ok") is True
    assert report.get("reason") == "ok"
