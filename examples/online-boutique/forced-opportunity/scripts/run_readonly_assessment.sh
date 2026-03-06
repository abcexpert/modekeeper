#!/usr/bin/env bash
set -Eeuo pipefail

if [[ $# -lt 3 || $# -gt 4 ]]; then
  echo "usage: $0 <namespace> <deployment> <out_dir> [observe_duration]" >&2
  exit 2
fi

NAMESPACE="$1"
DEPLOYMENT="$2"
OUT_DIR="$3"
OBSERVE_DURATION="${4:-60s}"

mkdir -p "$OUT_DIR"

mk eval k8s \
  --k8s-namespace "$NAMESPACE" \
  --k8s-deployment "$DEPLOYMENT" \
  --observe-duration "$OBSERVE_DURATION" \
  --out "$OUT_DIR/eval_k8s"

mk closed-loop run \
  --scenario drift \
  --dry-run \
  --observe-source k8s \
  --k8s-namespace "$NAMESPACE" \
  --k8s-deployment "$DEPLOYMENT" \
  --observe-duration "$OBSERVE_DURATION" \
  --out "$OUT_DIR/closed_loop"

mk closed-loop watch \
  --scenario drift \
  --dry-run \
  --observe-source k8s \
  --k8s-namespace "$NAMESPACE" \
  --k8s-deployment "$DEPLOYMENT" \
  --observe-duration "$OBSERVE_DURATION" \
  --out "$OUT_DIR/watch" \
  --max-iterations 1 \
  --interval 0s
