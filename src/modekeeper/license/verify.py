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
    reason_code: str,
    failure_code: str | None,
    failure_detail: str | None,
    kid: str | None,
    issuer: str | None,
    expires_at: int | None,
    entitlements: list[str],
) -> dict:
    return {
        "schema_version": "license_verify.v0",
        "license_ok": bool(license_ok),
        "reason": reason,
        "reason_code": reason_code,
        "failure_code": failure_code,
        "failure_detail": failure_detail,
        "kid": kid,
        "issuer": issuer,
        "expiry": expires_at,
        "expires_at": expires_at,
        "entitlements": entitlements,
        "entitlements_summary": entitlements,
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


def _normalized_entitlements(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return sorted({item.strip() for item in value if isinstance(item, str) and item.strip()})


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


def _normalize_keyring(payload: object) -> dict[str, str]:
    if not isinstance(payload, dict):
        return {}
    normalized: dict[str, str] = {}
    for raw_kid, raw_pubkey in payload.items():
        if not isinstance(raw_kid, str) or not raw_kid.strip():
            continue
        if not isinstance(raw_pubkey, str) or not raw_pubkey.strip():
            continue
        try:
            pub_raw = base64.b64decode(raw_pubkey, validate=True)
        except Exception:
            continue
        if len(pub_raw) != 32:
            continue
        normalized[raw_kid] = raw_pubkey
    return dict(sorted(normalized.items(), key=lambda item: item[0]))


def _load_trust_chain_issuer_keys(
    *,
    issuer_keyset_path: Path | None,
    root_keys: dict[str, str],
) -> tuple[dict[str, str] | None, str | None, str | None]:
    if issuer_keyset_path is None:
        return None, "issuer_keyset_missing", "issuer_keyset_path_required_in_trust_chain_mode"

    try:
        raw = issuer_keyset_path.read_text(encoding="utf-8")
    except Exception:
        return None, "issuer_keyset_io_error", "issuer_keyset_path_unreadable"

    try:
        data = json.loads(raw)
    except Exception:
        return None, "issuer_keyset_invalid_json", "issuer_keyset_payload_not_json_object"

    if not isinstance(data, dict):
        return None, "issuer_keyset_invalid_shape", "issuer_keyset_payload_not_object"

    if data.get("schema_version") != "issuer_keyset.v1":
        return None, "issuer_keyset_schema_unsupported", "schema_version_must_be_issuer_keyset_v1"

    root_kid = data.get("root_kid")
    if not isinstance(root_kid, str) or not root_kid.strip():
        return None, "issuer_keyset_root_kid_invalid", "root_kid_must_be_non_empty_string"
    selected_root_pubkey = root_keys.get(root_kid)
    if not isinstance(selected_root_pubkey, str) or not selected_root_pubkey.strip():
        return None, "issuer_keyset_unknown_root_kid", "root_kid_not_in_root_public_key_allowlist"

    signature = data.get("signature")
    if not isinstance(signature, str) or not signature.strip():
        return None, "issuer_keyset_signature_missing", "signature_must_be_non_empty_base64_string"

    issuer_keys = _normalize_keyring(data.get("keys"))
    if not issuer_keys:
        return None, "issuer_keyset_keys_invalid", "keys_must_be_non_empty_map_of_kid_to_public_key"

    payload = dict(data)
    payload.pop("signature", None)
    if not _verify_signature(payload, signature, [selected_root_pubkey]):
        return None, "issuer_keyset_signature_invalid", "issuer_keyset_signature_does_not_match_selected_root_key"
    return issuer_keys, None, None


def verify_license(
    path: Path,
    now_ts: int | None = None,
    kubectl: str = "kubectl",
    *,
    trust_chain: bool = False,
    issuer_keyset_path: Path | None = None,
    public_keys_path: Path | None = None,
) -> dict:
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
            reason_code="license_invalid",
            failure_code="license_io_error",
            failure_detail="license_path_unreadable",
            kid=None,
            issuer=None,
            expires_at=None,
            entitlements=[],
        )

    try:
        data = json.loads(raw)
    except Exception:
        return _result(
            license_ok=False,
            reason="license_invalid",
            reason_code="license_invalid",
            failure_code="license_invalid_json",
            failure_detail="license_payload_not_json_object",
            kid=None,
            issuer=None,
            expires_at=None,
            entitlements=[],
        )

    if not isinstance(data, dict):
        return _result(
            license_ok=False,
            reason="license_invalid",
            reason_code="license_invalid",
            failure_code="license_invalid_shape",
            failure_detail="license_payload_not_object",
            kid=None,
            issuer=None,
            expires_at=None,
            entitlements=[],
        )

    schema_version = data.get("schema_version")
    org = data.get("org")
    issued_at = data.get("issued_at")
    expires_at = data.get("expires_at")
    entitlements = data.get("entitlements")
    bindings = data.get("bindings")
    kid = data.get("kid")
    issuer = data.get("issuer")
    signature = data.get("signature")
    normalized_entitlements = _normalized_entitlements(entitlements)
    normalized_kid = kid.strip() if isinstance(kid, str) and kid.strip() else None
    normalized_issuer = issuer.strip() if isinstance(issuer, str) and issuer.strip() else None

    if schema_version != "license.v1":
        return _result(
            license_ok=False,
            reason="license_invalid",
            reason_code="license_invalid",
            failure_code="license_schema_unsupported",
            failure_detail="schema_version_must_be_license_v1",
            kid=normalized_kid,
            issuer=normalized_issuer,
            expires_at=expires_at if _is_int_epoch(expires_at) else None,
            entitlements=normalized_entitlements,
        )
    if not isinstance(org, str) or not org.strip():
        return _result(
            license_ok=False,
            reason="license_invalid",
            reason_code="license_invalid",
            failure_code="license_org_invalid",
            failure_detail="org_must_be_non_empty_string",
            kid=normalized_kid,
            issuer=normalized_issuer,
            expires_at=expires_at if _is_int_epoch(expires_at) else None,
            entitlements=normalized_entitlements,
        )
    if not _is_int_epoch(issued_at) or not _is_int_epoch(expires_at):
        return _result(
            license_ok=False,
            reason="license_invalid",
            reason_code="license_invalid",
            failure_code="license_time_fields_invalid",
            failure_detail="issued_at_and_expires_at_must_be_int_epoch",
            kid=normalized_kid,
            issuer=normalized_issuer,
            expires_at=expires_at if _is_int_epoch(expires_at) else None,
            entitlements=normalized_entitlements,
        )
    if not isinstance(entitlements, list) or not all(isinstance(x, str) for x in entitlements):
        return _result(
            license_ok=False,
            reason="license_invalid",
            reason_code="license_invalid",
            failure_code="license_entitlements_invalid",
            failure_detail="entitlements_must_be_list_of_strings",
            kid=normalized_kid,
            issuer=normalized_issuer,
            expires_at=expires_at,
            entitlements=[],
        )
    if bindings is not None and not isinstance(bindings, dict):
        return _result(
            license_ok=False,
            reason="license_invalid",
            reason_code="license_invalid",
            failure_code="license_bindings_invalid",
            failure_detail="bindings_must_be_object_when_present",
            kid=normalized_kid,
            issuer=normalized_issuer,
            expires_at=expires_at,
            entitlements=normalized_entitlements,
        )
    if kid is not None and (not isinstance(kid, str) or not kid.strip()):
        return _result(
            license_ok=False,
            reason="license_invalid",
            reason_code="license_invalid",
            failure_code="license_kid_invalid",
            failure_detail="kid_must_be_non_empty_string_when_present",
            kid=None,
            issuer=normalized_issuer,
            expires_at=expires_at,
            entitlements=normalized_entitlements,
        )
    if issuer is not None and (not isinstance(issuer, str) or not issuer.strip()):
        return _result(
            license_ok=False,
            reason="license_invalid",
            reason_code="license_invalid",
            failure_code="license_issuer_invalid",
            failure_detail="issuer_must_be_non_empty_string_when_present",
            kid=normalized_kid,
            issuer=None,
            expires_at=expires_at,
            entitlements=normalized_entitlements,
        )
    if not isinstance(signature, str) or not signature.strip():
        return _result(
            license_ok=False,
            reason="license_invalid",
            reason_code="license_invalid",
            failure_code="license_signature_missing",
            failure_detail="signature_must_be_non_empty_base64_string",
            kid=normalized_kid,
            issuer=normalized_issuer,
            expires_at=expires_at,
            entitlements=normalized_entitlements,
        )

    if trust_chain:
        root_keys = load_public_keys(path=public_keys_path)
        if not root_keys:
            return _result(
                license_ok=False,
                reason="license_invalid",
                reason_code="license_invalid",
                failure_code="root_public_keys_unavailable",
                failure_detail="root_public_key_allowlist_empty_or_invalid",
                kid=normalized_kid,
                issuer=normalized_issuer,
                expires_at=expires_at,
                entitlements=normalized_entitlements,
            )
        kid_to_pubkey_b64, failure_code, failure_detail = _load_trust_chain_issuer_keys(
            issuer_keyset_path=issuer_keyset_path,
            root_keys=root_keys,
        )
        if kid_to_pubkey_b64 is None:
            return _result(
                license_ok=False,
                reason="license_invalid",
                reason_code="license_invalid",
                failure_code=failure_code,
                failure_detail=failure_detail,
                kid=normalized_kid,
                issuer=normalized_issuer,
                expires_at=expires_at,
                entitlements=normalized_entitlements,
            )
    else:
        kid_to_pubkey_b64 = load_public_keys(path=public_keys_path)
        if not kid_to_pubkey_b64:
            return _result(
                license_ok=False,
                reason="license_invalid",
                reason_code="license_invalid",
                failure_code="public_keys_unavailable",
                failure_detail="public_key_allowlist_empty_or_invalid",
                kid=normalized_kid,
                issuer=normalized_issuer,
                expires_at=expires_at,
                entitlements=normalized_entitlements,
            )

    key_b64_candidates: list[str]
    if isinstance(kid, str):
        selected = kid_to_pubkey_b64.get(kid)
        if not isinstance(selected, str) or not selected.strip():
            return _result(
                license_ok=False,
                reason="license_invalid",
                reason_code="license_invalid",
                failure_code="license_unknown_issuer_kid" if trust_chain else "license_unknown_kid",
                failure_detail=(
                    "license_kid_not_in_issuer_keyset"
                    if trust_chain
                    else "license_kid_not_in_public_key_allowlist"
                ),
                kid=normalized_kid,
                issuer=normalized_issuer,
                expires_at=expires_at,
                entitlements=normalized_entitlements,
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
            reason_code="license_invalid",
            failure_code="license_signature_invalid",
            failure_detail="signature_does_not_match_selected_public_key",
            kid=normalized_kid,
            issuer=normalized_issuer,
            expires_at=expires_at,
            entitlements=normalized_entitlements,
        )

    if issued_at >= expires_at:
        return _result(
            license_ok=False,
            reason="license_invalid",
            reason_code="license_invalid",
            failure_code="license_time_window_invalid",
            failure_detail="issued_at_must_be_less_than_expires_at",
            kid=normalized_kid,
            issuer=normalized_issuer,
            expires_at=expires_at,
            entitlements=normalized_entitlements,
        )
    if now_ts < issued_at:
        return _result(
            license_ok=False,
            reason="license_invalid",
            reason_code="license_invalid",
            failure_code="license_not_yet_valid",
            failure_detail="current_time_before_issued_at",
            kid=normalized_kid,
            issuer=normalized_issuer,
            expires_at=expires_at,
            entitlements=normalized_entitlements,
        )
    if now_ts >= expires_at:
        return _result(
            license_ok=False,
            reason="license_expired",
            reason_code="license_expired",
            failure_code="license_expired",
            failure_detail="current_time_on_or_after_expires_at",
            kid=normalized_kid,
            issuer=normalized_issuer,
            expires_at=expires_at,
            entitlements=normalized_entitlements,
        )

    if isinstance(bindings, dict) and "kube_context" in bindings:
        kube_context = bindings.get("kube_context")
        if not isinstance(kube_context, str) or not kube_context.strip():
            return _result(
                license_ok=False,
                reason="license_invalid",
                reason_code="license_invalid",
                failure_code="license_binding_invalid",
                failure_detail="bindings.kube_context_must_be_non_empty_string",
                kid=normalized_kid,
                issuer=normalized_issuer,
                expires_at=expires_at,
                entitlements=normalized_entitlements,
            )
        current = _current_kube_context(kubectl)
        if current is None or current != kube_context:
            return _result(
                license_ok=False,
                reason="binding_mismatch",
                reason_code="binding_mismatch",
                failure_code="license_binding_mismatch",
                failure_detail="kube_context_binding_mismatch",
                kid=normalized_kid,
                issuer=normalized_issuer,
                expires_at=expires_at,
                entitlements=normalized_entitlements,
            )

    return _result(
        license_ok=True,
        reason="ok",
        reason_code="ok",
        failure_code=None,
        failure_detail=None,
        kid=normalized_kid,
        issuer=normalized_issuer,
        expires_at=expires_at,
        entitlements=normalized_entitlements,
    )
