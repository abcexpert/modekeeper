#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
FIXTURE="$ROOT_DIR/fixture.yaml"
NS_RBAC="$ROOT_DIR/ns_get_rbac.yaml"
KUBECONFIG_OUT="$ROOT_DIR/kubeconfig.mk055"
REPORT_OUT="report/mk060_rbac_replay"

kubectl apply -f "$FIXTURE"
kubectl apply -f "$NS_RBAC"

SA_TOKEN=$(kubectl -n mk055-rbac-deny create token mk055-no-patch)
APISERVER=$(kubectl config view --minify -o jsonpath='{.clusters[0].cluster.server}')

cat > "$KUBECONFIG_OUT" <<EOF_KC
apiVersion: v1
kind: Config
clusters:
- name: mk055
  cluster:
    server: ${APISERVER}
    insecure-skip-tls-verify: true
users:
- name: mk055-no-patch
  user:
    token: ${SA_TOKEN}
contexts:
- name: mk055
  context:
    cluster: mk055
    user: mk055-no-patch
    namespace: mk055-rbac-deny
current-context: mk055
EOF_KC

KUBECONFIG="$KUBECONFIG_OUT" mk k8s verify \
  --plan docs/evidence/mk055/k8s_plan.json \
  --out "$REPORT_OUT"

printf '\nWrote kubeconfig: %s\n' "$KUBECONFIG_OUT"
printf 'Report output: %s\n' "$REPORT_OUT"
