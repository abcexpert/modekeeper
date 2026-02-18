"""Allowlisted Ed25519 public keys (base64, raw 32-byte) keyed by kid."""

from __future__ import annotations

import base64
import json
import os
from pathlib import Path


def load_public_keys(path: Path | None = None) -> dict[str, str]:
    """Load key allowlist from JSON map {kid -> public_key_b64_raw32}."""
    if path is not None:
        source = path
    else:
        env_path = os.environ.get("MODEKEEPER_LICENSE_PUBLIC_KEYS_PATH")
        if env_path:
            source = Path(env_path)
        else:
            home_default = Path.home() / ".config" / "modekeeper" / "license_public_keys.json"
            source = home_default if home_default.exists() else Path(__file__).with_name("public_keys.json")
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except Exception:
        return {}
    if not isinstance(payload, dict):
        return {}

    normalized: dict[str, str] = {}
    for kid, pubkey in payload.items():
        if not isinstance(kid, str) or not kid.strip():
            continue
        if not isinstance(pubkey, str) or not pubkey.strip():
            continue
        try:
            pub_raw = base64.b64decode(pubkey, validate=True)
        except Exception:
            continue
        if len(pub_raw) != 32:
            continue
        normalized[kid] = pubkey
    return dict(sorted(normalized.items(), key=lambda item: item[0]))


KID_TO_PUBKEY_B64 = load_public_keys()
