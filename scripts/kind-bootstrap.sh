#!/usr/bin/env bash
set -Eeuo pipefail

err() {
  echo "error: $*" >&2
  exit 1
}

log() {
  printf '==> %s\n' "$*"
}

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || err "missing required command: $1"
}

list_trainer_pods() {
  local pods_json
  pods_json="$(kubectl get pods -l app=trainer -o json 2>/dev/null || true)"
  [[ -n "$pods_json" ]] || return 0

  python3 - "$pods_json" <<'PY' 2>/dev/null || true
import json
import sys

def ts_value(pod):
    meta = pod.get("metadata", {}) if isinstance(pod, dict) else {}
    ts = meta.get("creationTimestamp")
    return ts if isinstance(ts, str) else ""

def name_value(pod):
    meta = pod.get("metadata", {}) if isinstance(pod, dict) else {}
    name = meta.get("name")
    return name if isinstance(name, str) else ""

def is_ready_running(pod):
    if not isinstance(pod, dict):
        return False
    status = pod.get("status", {})
    if not isinstance(status, dict):
        return False
    if status.get("phase") != "Running":
        return False
    container_statuses = status.get("containerStatuses", [])
    if not isinstance(container_statuses, list):
        return False
    for c in container_statuses:
        if isinstance(c, dict) and c.get("name") == "trainer" and c.get("ready") is True:
            return True
    return False

try:
    payload = json.loads(sys.argv[1])
except Exception:
    raise SystemExit(0)

if not isinstance(payload, dict):
    raise SystemExit(0)
items = payload.get("items")
if not isinstance(items, list) or not items:
    raise SystemExit(0)

pods = [p for p in items if isinstance(p, dict)]
if not pods:
    raise SystemExit(0)

ready_running = sorted(
    [p for p in pods if is_ready_running(p)],
    key=ts_value,
    reverse=True,
)
remaining = sorted(
    [p for p in pods if not is_ready_running(p)],
    key=ts_value,
    reverse=True,
)

for pod in ready_running + remaining:
    name = name_value(pod)
    if name:
        print(name)
PY
}

pick_trainer_pod() {
  list_trainer_pods | head -n 1
}

tail_trainer_logs_for_pod() {
  local pod_name="$1"
  local logs

  logs="$(kubectl logs "$pod_name" -c trainer --tail=5 2>/dev/null || true)"
  if [[ -n "$logs" ]]; then
    printf "%s\n" "$logs"
    return 0
  fi

  kubectl logs "$pod_name" -c trainer --previous --tail=5 2>/dev/null || true
}

need_cmd kind
need_cmd kubectl
need_cmd docker
need_cmd python3

cluster_name="modekeeper"
context_name="kind-modekeeper"

if ! kind get clusters | grep -Fxq "$cluster_name"; then
  log "kind cluster '$cluster_name' not found; creating..."
  kind create cluster --name "$cluster_name"
fi

current_context="$(kubectl config current-context 2>/dev/null || true)"
if [[ "$current_context" != "$context_name" ]]; then
  log "switching kubectl context to '$context_name'"
  kubectl config use-context "$context_name" >/dev/null
fi

if kubectl get deployment trainer >/dev/null 2>&1; then
  containers="$(kubectl get deployment trainer -o jsonpath='{.spec.template.spec.containers[*].name}')"
  if [[ "$containers" != "trainer" ]]; then
    log "deployment/trainer is non-canonical (containers: ${containers:-<none>}); deleting..."
    kubectl delete deployment trainer
  fi
fi

log "building modekeeper-trainer:dev"
docker build -f docker/trainer/Dockerfile -t modekeeper-trainer:dev .

log "loading modekeeper-trainer:dev into kind cluster '$cluster_name'"
kind load docker-image modekeeper-trainer:dev --name "$cluster_name"

log "applying k8s/trainer-minimal.yaml"
kubectl apply -f k8s/trainer-minimal.yaml

log "waiting for deployment/trainer rollout"
kubectl rollout status deployment/trainer --timeout=120s

log "waiting for terminating trainer pods to clear (max ~60s)"
for _ in $(seq 1 30); do
  terminating="$(kubectl get pods -l app=trainer -o jsonpath='{.items[?(@.metadata.deletionTimestamp)].metadata.name}' 2>/dev/null || true)"
  if [[ -z "${terminating// }" ]]; then
    break
  fi
  sleep 2
done

log "showing running trainer pods"
kubectl get pods -l app=trainer --field-selector=status.phase=Running -o wide

pod="$(pick_trainer_pod)"
if [[ -z "$pod" ]]; then
  err "no pod found for app=trainer"
fi
log "tailing logs from $pod"
tail_trainer_logs_for_pod "$pod"
