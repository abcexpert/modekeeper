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
STATE_DIR="${TMPDIR:-/tmp}/modekeeper-forced-opportunity"
STATE_FILE="$STATE_DIR/${NAMESPACE}_${SCENARIO}.state"

if [[ ! -f "$MANIFEST_PATH" ]]; then
  echo "manifest not found: $MANIFEST_PATH" >&2
  exit 2
fi

mkdir -p "$STATE_DIR"

yaml_or_null() {
  local value="${1:-}"
  if [[ -z "$value" ]]; then
    echo "null"
  else
    printf '"%s"\n' "$value"
  fi
}

apply_patch_scenario() {
  case "$SCENARIO" in
    oversized_requests)
      local deployment="frontend"
      local container="server"
      local req_cpu req_memory lim_cpu lim_memory
      req_cpu="$(kubectl -n "$NAMESPACE" get deployment "$deployment" -o jsonpath="{.spec.template.spec.containers[?(@.name==\"$container\")].resources.requests.cpu}")"
      req_memory="$(kubectl -n "$NAMESPACE" get deployment "$deployment" -o jsonpath="{.spec.template.spec.containers[?(@.name==\"$container\")].resources.requests.memory}")"
      lim_cpu="$(kubectl -n "$NAMESPACE" get deployment "$deployment" -o jsonpath="{.spec.template.spec.containers[?(@.name==\"$container\")].resources.limits.cpu}")"
      lim_memory="$(kubectl -n "$NAMESPACE" get deployment "$deployment" -o jsonpath="{.spec.template.spec.containers[?(@.name==\"$container\")].resources.limits.memory}")"
      cat >"$STATE_FILE" <<EOF
DEPLOYMENT=$deployment
CONTAINER=$container
REQ_CPU=$req_cpu
REQ_MEMORY=$req_memory
LIM_CPU=$lim_cpu
LIM_MEMORY=$lim_memory
EOF
      kubectl -n "$NAMESPACE" patch deployment "$deployment" --type=strategic --patch-file "$MANIFEST_PATH"
      ;;
    replica_overprovisioning)
      local deployment="emailservice"
      local replicas
      replicas="$(kubectl -n "$NAMESPACE" get deployment "$deployment" -o jsonpath='{.spec.replicas}')"
      cat >"$STATE_FILE" <<EOF
DEPLOYMENT=$deployment
REPLICAS=$replicas
EOF
      kubectl -n "$NAMESPACE" patch deployment "$deployment" --type=strategic --patch-file "$MANIFEST_PATH"
      ;;
    *)
      echo "unknown patch scenario: $SCENARIO" >&2
      exit 2
      ;;
  esac
}

delete_patch_scenario() {
  if [[ ! -f "$STATE_FILE" ]]; then
    echo "state not found for patch scenario cleanup: $STATE_FILE" >&2
    echo "re-apply once or restore baseline deployment config manually." >&2
    exit 1
  fi

  # shellcheck disable=SC1090
  source "$STATE_FILE"

  case "$SCENARIO" in
    oversized_requests)
      local req_cpu_patch req_memory_patch lim_cpu_patch lim_memory_patch
      req_cpu_patch="$(yaml_or_null "${REQ_CPU:-}")"
      req_memory_patch="$(yaml_or_null "${REQ_MEMORY:-}")"
      lim_cpu_patch="$(yaml_or_null "${LIM_CPU:-}")"
      lim_memory_patch="$(yaml_or_null "${LIM_MEMORY:-}")"
      kubectl -n "$NAMESPACE" patch deployment "${DEPLOYMENT:-frontend}" --type=strategic --patch "
spec:
  template:
    spec:
      containers:
      - name: ${CONTAINER:-server}
        resources:
          requests:
            cpu: $req_cpu_patch
            memory: $req_memory_patch
          limits:
            cpu: $lim_cpu_patch
            memory: $lim_memory_patch
"
      ;;
    replica_overprovisioning)
      kubectl -n "$NAMESPACE" patch deployment "${DEPLOYMENT:-emailservice}" --type=strategic --patch "
spec:
  replicas: ${REPLICAS:-1}
"
      ;;
    *)
      echo "unknown patch scenario: $SCENARIO" >&2
      exit 2
      ;;
  esac

  rm -f "$STATE_FILE"
}

case "$ACTION" in
  apply)
    case "$SCENARIO" in
      oversized_requests|replica_overprovisioning)
        apply_patch_scenario
        ;;
      burst_traffic)
        kubectl -n "$NAMESPACE" apply -f "$MANIFEST_PATH"
        ;;
      *)
        echo "unknown scenario: $SCENARIO" >&2
        exit 2
        ;;
    esac
    ;;
  delete)
    case "$SCENARIO" in
      oversized_requests|replica_overprovisioning)
        delete_patch_scenario
        ;;
      burst_traffic)
        kubectl -n "$NAMESPACE" delete -f "$MANIFEST_PATH" --ignore-not-found=true
        ;;
      *)
        echo "unknown scenario: $SCENARIO" >&2
        exit 2
        ;;
    esac
    ;;
  *)
    echo "unknown action: $ACTION" >&2
    exit 2
    ;;
esac
