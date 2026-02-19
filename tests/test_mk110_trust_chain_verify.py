import base64
import json
import subprocess
from pathlib import Path

import pytest
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


def _private_key(fill: int) -> Ed25519PrivateKey:
    return Ed25519PrivateKey.from_private_bytes(bytes([fill]) * 32)


def _public_key_b64(private_key: Ed25519PrivateKey) -> str:
    raw = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return base64.b64encode(raw).decode("ascii")


def _sign(payload: dict, private_key: Ed25519PrivateKey) -> str:
    signature = private_key.sign(canonical_json_bytes(payload))
    return base64.b64encode(signature).decode("ascii")


def _write_license(path: Path, payload: dict, issuer_private_key: Ed25519PrivateKey) -> None:
    license_data = {**payload, "signature": _sign(payload, issuer_private_key)}
    path.write_text(
        json.dumps(license_data, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _write_issuer_keyset(
    path: Path,
    *,
    root_kid: str,
    issuer_keys: dict[str, str],
    root_private_key: Ed25519PrivateKey,
) -> None:
    payload = {
        "schema_version": "issuer_keyset.v1",
        "root_kid": root_kid,
        "keys": issuer_keys,
    }
    keyset = {**payload, "signature": _sign(payload, root_private_key)}
    path.write_text(
        json.dumps(keyset, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _verify_with_trust_chain(
    *,
    mk_path: Path,
    out_dir: Path,
    license_path: Path,
    issuer_keyset_path: Path,
    root_keys_path: Path,
) -> dict:
    cp = _run(
        mk_path,
        [
            "license",
            "verify",
            "--license",
            str(license_path),
            "--trust-chain",
            "--issuer-keyset",
            str(issuer_keyset_path),
            "--root-public-keys",
            str(root_keys_path),
            "--out",
            str(out_dir),
        ],
    )
    report = json.loads((out_dir / "license_verify_latest.json").read_text(encoding="utf-8"))
    report["__rc__"] = cp.returncode
    return report


def test_mk110_trust_chain_happy_path(tmp_path: Path, mk_path: Path) -> None:
    root_private_key = _private_key(11)
    issuer_private_key = _private_key(22)
    issuer_kid = "issuer-2026-02"

    root_keys_path = tmp_path / "root_keys.json"
    root_keys_path.write_text(
        json.dumps({"root-2026-01": _public_key_b64(root_private_key)}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    issuer_keyset_path = tmp_path / "issuer_keyset.json"
    _write_issuer_keyset(
        issuer_keyset_path,
        root_kid="root-2026-01",
        issuer_keys={issuer_kid: _public_key_b64(issuer_private_key)},
        root_private_key=root_private_key,
    )

    payload = {
        "schema_version": "license.v1",
        "org": "Acme",
        "issued_at": 1700000000,
        "expires_at": 4102444800,
        "entitlements": ["apply", "observe"],
        "kid": issuer_kid,
    }
    license_path = tmp_path / "license.json"
    _write_license(license_path, payload, issuer_private_key)

    out_dir = tmp_path / "out_ok"
    report = _verify_with_trust_chain(
        mk_path=mk_path,
        out_dir=out_dir,
        license_path=license_path,
        issuer_keyset_path=issuer_keyset_path,
        root_keys_path=root_keys_path,
    )
    assert report["__rc__"] == 0
    assert report["license_ok"] is True
    assert report["reason"] == "ok"
    assert report["kid"] == issuer_kid


@pytest.mark.parametrize(
    ("case_name", "mutate_keyset", "expected_failure"),
    [
        (
            "unknown_root_kid",
            lambda keyset: {**keyset, "root_kid": "root-unknown"},
            "issuer_keyset_unknown_root_kid",
        ),
        (
            "bad_signature",
            lambda keyset: {**keyset, "signature": "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=="},
            "issuer_keyset_signature_invalid",
        ),
    ],
)
def test_mk110_trust_chain_blocks_on_unknown_root_or_bad_signature(
    tmp_path: Path,
    mk_path: Path,
    case_name: str,
    mutate_keyset,
    expected_failure: str,
) -> None:
    root_private_key = _private_key(33)
    issuer_private_key = _private_key(44)
    issuer_kid = "issuer-2026-03"

    root_keys_path = tmp_path / f"{case_name}_root_keys.json"
    root_keys_path.write_text(
        json.dumps({"root-2026-02": _public_key_b64(root_private_key)}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    keyset_payload = {
        "schema_version": "issuer_keyset.v1",
        "root_kid": "root-2026-02",
        "keys": {issuer_kid: _public_key_b64(issuer_private_key)},
    }
    keyset = {**keyset_payload, "signature": _sign(keyset_payload, root_private_key)}
    keyset = mutate_keyset(keyset)
    issuer_keyset_path = tmp_path / f"{case_name}_issuer_keyset.json"
    issuer_keyset_path.write_text(
        json.dumps(keyset, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    payload = {
        "schema_version": "license.v1",
        "org": "Acme",
        "issued_at": 1700000000,
        "expires_at": 4102444800,
        "entitlements": ["apply"],
        "kid": issuer_kid,
    }
    license_path = tmp_path / f"{case_name}_license.json"
    _write_license(license_path, payload, issuer_private_key)

    out_dir = tmp_path / f"{case_name}_out"
    report = _verify_with_trust_chain(
        mk_path=mk_path,
        out_dir=out_dir,
        license_path=license_path,
        issuer_keyset_path=issuer_keyset_path,
        root_keys_path=root_keys_path,
    )
    assert report["__rc__"] == 2
    assert report["license_ok"] is False
    assert report["reason"] == "license_invalid"
    assert report["failure_code"] == expected_failure


def test_mk110_trust_chain_blocks_when_issuer_kid_missing(tmp_path: Path, mk_path: Path) -> None:
    root_private_key = _private_key(55)
    issuer_private_key = _private_key(66)

    root_keys_path = tmp_path / "root_keys.json"
    root_keys_path.write_text(
        json.dumps({"root-2026-03": _public_key_b64(root_private_key)}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    issuer_keyset_path = tmp_path / "issuer_keyset.json"
    _write_issuer_keyset(
        issuer_keyset_path,
        root_kid="root-2026-03",
        issuer_keys={"issuer-2026-04": _public_key_b64(issuer_private_key)},
        root_private_key=root_private_key,
    )

    payload = {
        "schema_version": "license.v1",
        "org": "Acme",
        "issued_at": 1700000000,
        "expires_at": 4102444800,
        "entitlements": ["apply"],
        "kid": "issuer-unknown",
    }
    license_path = tmp_path / "license_missing_kid.json"
    _write_license(license_path, payload, issuer_private_key)

    out_dir = tmp_path / "out_missing_kid"
    report = _verify_with_trust_chain(
        mk_path=mk_path,
        out_dir=out_dir,
        license_path=license_path,
        issuer_keyset_path=issuer_keyset_path,
        root_keys_path=root_keys_path,
    )
    assert report["__rc__"] == 2
    assert report["license_ok"] is False
    assert report["reason"] == "license_invalid"
    assert report["failure_code"] == "license_unknown_issuer_kid"
    assert report["failure_detail"] == "license_kid_not_in_issuer_keyset"

