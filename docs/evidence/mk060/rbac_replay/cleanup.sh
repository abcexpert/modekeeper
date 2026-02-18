#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
FIXTURE="$ROOT_DIR/fixture.yaml"
NS_RBAC="$ROOT_DIR/ns_get_rbac.yaml"
KUBECONFIG_OUT="$ROOT_DIR/kubeconfig.mk055"
REPORT_OUT="report/mk060_rbac_replay"

kubectl delete -f "$NS_RBAC" --ignore-not-found
kubectl delete -f "$FIXTURE" --ignore-not-found

rm -f "$KUBECONFIG_OUT"
rm -rf "$REPORT_OUT"
