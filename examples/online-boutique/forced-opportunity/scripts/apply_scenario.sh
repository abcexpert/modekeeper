#!/usr/bin/env bash
set -Eeuo pipefail

if [[ $# -lt 2 || $# -gt 3 ]]; then
  echo "usage: $0 <apply|delete> <oversized_requests|replica_overprovisioning|burst_traffic> [namespace]" >&2
  exit 2
fi

ACTION="$1"
SCENARIO="$2"
NAMESPACE="${3:-default}"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
MANIFEST_REL="$($SCRIPT_DIR/scenario_manifest.sh "$SCENARIO")"
MANIFEST_PATH="$ROOT_DIR/$MANIFEST_REL"

if [[ ! -f "$MANIFEST_PATH" ]]; then
  echo "manifest not found: $MANIFEST_PATH" >&2
  exit 2
fi

case "$ACTION" in
  apply)
    kubectl -n "$NAMESPACE" apply -f "$MANIFEST_PATH"
    ;;
  delete)
    kubectl -n "$NAMESPACE" delete -f "$MANIFEST_PATH" --ignore-not-found=true
    ;;
  *)
    echo "unknown action: $ACTION" >&2
    exit 2
    ;;
esac
