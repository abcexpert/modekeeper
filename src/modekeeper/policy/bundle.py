"""Policy bundle artifact helpers."""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path


SCHEMA_VERSION = "policy_bundle.v1"
BUNDLE_VERSION = 1


def sha256_file(path: Path) -> str:
    hasher = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def build_policy_bundle(
    *,
    mk_version: str,
    policy_id: str,
    policy_version: str,
    policy_params: dict | None = None,
    git_commit: str | None = None,
    git_dirty: bool = False,
    host: str | None = None,
    passport_id: str | None = None,
    passport_sha256: str | None = None,
    chord_catalog_sha256: str | None = None,
    rollback_from_verify_report: str | None = None,
    rollback_plan_path: str | None = None,
    created_at: int | None = None,
) -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "bundle_version": BUNDLE_VERSION,
        "created_at": int(time.time()) if created_at is None else int(created_at),
        "mk_version": str(mk_version),
        "provenance": {
            "git_commit": git_commit,
            "git_dirty": bool(git_dirty),
            "host": host,
        },
        "policy": {
            "id": str(policy_id),
            "version": str(policy_version),
            "params": policy_params if isinstance(policy_params, dict) else {},
        },
        "inputs": {
            "passport_id": passport_id,
            "passport_sha256": passport_sha256,
            "chord_catalog_sha256": chord_catalog_sha256,
        },
        "rollback": {
            "mode": "skeleton",
            "from_verify_report": rollback_from_verify_report,
            "rollback_plan_path": rollback_plan_path,
        },
    }


def write_policy_bundle(out_dir: Path, bundle: dict) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "policy_bundle_latest.json"
    out_path.write_text(
        json.dumps(bundle, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return out_path
