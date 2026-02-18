"""Offline license.v1 verification."""

from __future__ import annotations

import base64
import json
import subprocess
import time
from pathlib import Path

from modekeeper.license.canonical import canonical_json_bytes
from modekeeper.license.public_keys import load_public_keys

try:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
except Exception:  # pragma: no cover - import failure is handled as invalid license.
    Ed25519PublicKey = None  # type: ignore[assignment]


def _result(
    *,
    license_ok: bool,
    reason: str,
    expires_at: int | None,
    entitlements_summary: list[str],
) -> dict:
    return {
        "schema_version": "license_verify.v0",
        "license_ok": bool(license_ok),
        "reason": reason,
        "expires_at": expires_at,
        "entitlements_summary": entitlements_summary,
    }


def _is_int_epoch(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _current_kube_context(kubectl: str) -> str | None:
    try:
        cp = subprocess.run(
            [kubectl, "config", "current-context"],
            capture_output=True,
            text=True,
            timeout=20.0,
        )
    except Exception:
        return None
    if cp.returncode != 0:
        return None
    context = (cp.stdout or "").strip()
    if not context:
        return None
    return context


def _verify_signature(payload: dict, signature_b64: str, key_b64_candidates: list[str]) -> bool:
    if Ed25519PublicKey is None:
        return False
    try:
        signature = base64.b64decode(signature_b64, validate=True)
    except Exception:
        return False
    if len(signature) != 64:
        return False

    message = canonical_json_bytes(payload)
    for pub_b64 in key_b64_candidates:
        try:
            pub_raw = base64.b64decode(pub_b64, validate=True)
            if len(pub_raw) != 32:
                continue
            public_key = Ed25519PublicKey.from_public_bytes(pub_raw)
            public_key.verify(signature, message)
            return True
        except Exception:
            continue
    return False


def verify_license(path: Path, now_ts: int | None = None, kubectl: str = "kubectl") -> dict:
    """Verify license.v1 file and return license_verify.v0 payload."""
    if now_ts is None:
        now_ts = int(time.time())
    if not isinstance(now_ts, int):
        now_ts = int(now_ts)

    try:
        raw = path.read_text(encoding="utf-8")
    except Exception:
        return _result(
            license_ok=False,
            reason="license_invalid",
            expires_at=None,
            entitlements_summary=[],
        )

    try:
        data = json.loads(raw)
    except Exception:
        return _result(
            license_ok=False,
            reason="license_invalid",
            expires_at=None,
            entitlements_summary=[],
        )

    if not isinstance(data, dict):
        return _result(
            license_ok=False,
            reason="license_invalid",
            expires_at=None,
            entitlements_summary=[],
        )

    schema_version = data.get("schema_version")
    org = data.get("org")
    issued_at = data.get("issued_at")
    expires_at = data.get("expires_at")
    entitlements = data.get("entitlements")
    bindings = data.get("bindings")
    kid = data.get("kid")
    signature = data.get("signature")

    if schema_version != "license.v1":
        return _result(
            license_ok=False,
            reason="license_invalid",
            expires_at=expires_at if _is_int_epoch(expires_at) else None,
            entitlements_summary=[],
        )
    if not isinstance(org, str) or not org.strip():
        return _result(
            license_ok=False,
            reason="license_invalid",
            expires_at=expires_at if _is_int_epoch(expires_at) else None,
            entitlements_summary=[],
        )
    if not _is_int_epoch(issued_at) or not _is_int_epoch(expires_at):
        return _result(
            license_ok=False,
            reason="license_invalid",
            expires_at=expires_at if _is_int_epoch(expires_at) else None,
            entitlements_summary=[],
        )
    if not isinstance(entitlements, list) or not all(isinstance(x, str) for x in entitlements):
        return _result(
            license_ok=False,
            reason="license_invalid",
            expires_at=expires_at,
            entitlements_summary=[],
        )
    if bindings is not None and not isinstance(bindings, dict):
        return _result(
            license_ok=False,
            reason="license_invalid",
            expires_at=expires_at,
            entitlements_summary=[],
        )
    if kid is not None and (not isinstance(kid, str) or not kid.strip()):
        return _result(
            license_ok=False,
            reason="license_invalid",
            expires_at=expires_at,
            entitlements_summary=[],
        )
    if not isinstance(signature, str) or not signature.strip():
        return _result(
            license_ok=False,
            reason="license_invalid",
            expires_at=expires_at,
            entitlements_summary=[],
        )

    kid_to_pubkey_b64 = load_public_keys()

    key_b64_candidates: list[str]
    if isinstance(kid, str):
        selected = kid_to_pubkey_b64.get(kid)
        if not isinstance(selected, str) or not selected.strip():
            return _result(
                license_ok=False,
                reason="license_invalid",
                expires_at=expires_at,
                entitlements_summary=sorted({x.strip() for x in entitlements if x.strip()}),
            )
        key_b64_candidates = [selected]
    else:
        key_b64_candidates = list(kid_to_pubkey_b64.values())

    payload = dict(data)
    payload.pop("signature", None)
    if not _verify_signature(payload, signature, key_b64_candidates):
        return _result(
            license_ok=False,
            reason="license_invalid",
            expires_at=expires_at,
            entitlements_summary=sorted({x.strip() for x in entitlements if x.strip()}),
        )

    if issued_at >= expires_at:
        return _result(
            license_ok=False,
            reason="license_invalid",
            expires_at=expires_at,
            entitlements_summary=sorted({x.strip() for x in entitlements if x.strip()}),
        )
    if now_ts < issued_at:
        return _result(
            license_ok=False,
            reason="license_invalid",
            expires_at=expires_at,
            entitlements_summary=sorted({x.strip() for x in entitlements if x.strip()}),
        )
    if now_ts >= expires_at:
        return _result(
            license_ok=False,
            reason="license_expired",
            expires_at=expires_at,
            entitlements_summary=sorted({x.strip() for x in entitlements if x.strip()}),
        )

    if isinstance(bindings, dict) and "kube_context" in bindings:
        kube_context = bindings.get("kube_context")
        if not isinstance(kube_context, str) or not kube_context.strip():
            return _result(
                license_ok=False,
                reason="license_invalid",
                expires_at=expires_at,
                entitlements_summary=sorted({x.strip() for x in entitlements if x.strip()}),
            )
        current = _current_kube_context(kubectl)
        if current is None or current != kube_context:
            return _result(
                license_ok=False,
                reason="binding_mismatch",
                expires_at=expires_at,
                entitlements_summary=sorted({x.strip() for x in entitlements if x.strip()}),
            )

    return _result(
        license_ok=True,
        reason="ok",
        expires_at=expires_at,
        entitlements_summary=sorted({x.strip() for x in entitlements if x.strip()}),
    )
