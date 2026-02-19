import base64
import json
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from modekeeper.license.canonical import canonical_json_bytes
from modekeeper.license.verify import verify_license


def _sign(payload: dict, seed: bytes) -> str:
    private_key = Ed25519PrivateKey.from_private_bytes(seed)
    signature = private_key.sign(canonical_json_bytes(payload))
    return base64.b64encode(signature).decode("ascii")


def _write_license(path: Path, payload: dict, seed: bytes) -> None:
    license_data = {**payload, "signature": _sign(payload, seed)}
    path.write_text(
        json.dumps(license_data, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def test_license_verify_ok_with_known_kid(tmp_path: Path, monkeypatch) -> None:
    home_dir = tmp_path / "home"
    home_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("HOME", str(home_dir))
    monkeypatch.delenv("MODEKEEPER_LICENSE_PUBLIC_KEYS_PATH", raising=False)
    monkeypatch.delenv("MODEKEEPER_LICENSE_PATH", raising=False)

    payload = {
        "schema_version": "license.v1",
        "org": "Acme",
        "issued_at": 1700000000,
        "expires_at": 4102444800,
        "entitlements": ["apply"],
        "kid": "mk-dev-2026-01",
    }
    license_path = tmp_path / "license_known_kid.json"
    _write_license(license_path, payload, bytes(range(32)))

    report = verify_license(license_path, now_ts=1700000100)
    assert report["license_ok"] is True
    assert report["reason"] == "ok"
    assert report["kid"] == "mk-dev-2026-01"


def test_license_verify_blocked_with_unknown_kid(tmp_path: Path, monkeypatch) -> None:
    home_dir = tmp_path / "home"
    home_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("HOME", str(home_dir))
    monkeypatch.delenv("MODEKEEPER_LICENSE_PUBLIC_KEYS_PATH", raising=False)
    monkeypatch.delenv("MODEKEEPER_LICENSE_PATH", raising=False)

    payload = {
        "schema_version": "license.v1",
        "org": "Acme",
        "issued_at": 1700000000,
        "expires_at": 4102444800,
        "entitlements": ["apply"],
        "kid": "mk-dev-unknown",
    }
    license_path = tmp_path / "license_unknown_kid.json"
    _write_license(license_path, payload, bytes(range(32)))

    report = verify_license(license_path, now_ts=1700000100)
    assert report["license_ok"] is False
    assert report["reason"] == "license_invalid"
    assert report["failure_code"] == "license_unknown_kid"
    assert report["kid"] == "mk-dev-unknown"


def test_license_verify_rotation_uses_kid_selected_key(tmp_path: Path, monkeypatch) -> None:
    home_dir = tmp_path / "home"
    home_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("HOME", str(home_dir))
    monkeypatch.delenv("MODEKEEPER_LICENSE_PUBLIC_KEYS_PATH", raising=False)
    monkeypatch.delenv("MODEKEEPER_LICENSE_PATH", raising=False)

    payload = {
        "schema_version": "license.v1",
        "org": "Acme",
        "issued_at": 1700000000,
        "expires_at": 4102444800,
        "entitlements": ["apply", "observe"],
        "kid": "mk-dev-2026-02",
    }
    license_path = tmp_path / "license_rotated_kid.json"
    _write_license(license_path, payload, bytes(range(32, 64)))

    report = verify_license(license_path, now_ts=1700000100)
    assert report["license_ok"] is True
    assert report["reason"] == "ok"
    assert report["entitlements_summary"] == ["apply", "observe"]
    assert report["kid"] == "mk-dev-2026-02"


def test_license_verify_rotation_without_kid_falls_back_to_allowlist(tmp_path: Path, monkeypatch) -> None:
    home_dir = tmp_path / "home"
    home_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("HOME", str(home_dir))
    monkeypatch.delenv("MODEKEEPER_LICENSE_PUBLIC_KEYS_PATH", raising=False)
    monkeypatch.delenv("MODEKEEPER_LICENSE_PATH", raising=False)

    payload = {
        "schema_version": "license.v1",
        "org": "Acme",
        "issued_at": 1700000000,
        "expires_at": 4102444800,
        "entitlements": ["apply", "observe"],
    }
    license_path = tmp_path / "license_rotated_no_kid.json"
    _write_license(license_path, payload, bytes(range(32, 64)))

    report = verify_license(license_path, now_ts=1700000100)
    assert report["license_ok"] is True
    assert report["reason"] == "ok"
    assert report["entitlements_summary"] == ["apply", "observe"]
    assert report["kid"] is None
