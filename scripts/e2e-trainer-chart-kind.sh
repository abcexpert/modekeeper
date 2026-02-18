#!/usr/bin/env bash
set -Eeuo pipefail

cd "$(dirname "$0")/.."

err() {
  echo "ERROR: $*" >&2
  exit 2
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

trainer_knob_lines_for_pod() {
  local pod_name="$1"
  local logs
  local knob_lines

  logs="$(kubectl logs "$pod_name" -c trainer --tail=200 2>/dev/null || true)"
  knob_lines="$(printf "%s\n" "$logs" | grep '^modekeeper/knob' || true)"
  if [[ -n "$knob_lines" ]]; then
    printf "%s\n" "$knob_lines"
    return 0
  fi

  logs="$(kubectl logs "$pod_name" -c trainer --previous --tail=200 2>/dev/null || true)"
  knob_lines="$(printf "%s\n" "$logs" | grep '^modekeeper/knob' || true)"
  if [[ -n "$knob_lines" ]]; then
    printf "%s\n" "$knob_lines"
    return 0
  fi

  return 1
}

need_cmd kind
need_cmd kubectl
need_cmd docker
need_cmd helm
need_cmd python3

cluster_name="modekeeper"
context_name="kind-${cluster_name}"

if ! kind get clusters | grep -Fxq "$cluster_name"; then
  kind create cluster --name "$cluster_name"
fi

current_context="$(kubectl config current-context 2>/dev/null || true)"
if [[ "$current_context" != "$context_name" ]]; then
  kubectl config use-context "$context_name" >/dev/null
fi

docker build -f docker/trainer/Dockerfile -t modekeeper-trainer:dev .
kind load docker-image modekeeper-trainer:dev --name "$cluster_name"

helm uninstall trainer >/dev/null 2>&1 || true
kubectl delete deployment trainer serviceaccount trainer role trainer-pod-reader rolebinding trainer-pod-reader --ignore-not-found >/dev/null 2>&1 || true

helm upgrade --install trainer ./k8s/charts/trainer \
  --set image.repository=modekeeper-trainer \
  --set image.tag=dev \
  --set image.pullPolicy=IfNotPresent \
  --set loopIntervalSeconds=1 \
  --set knobs.alpha=1 \
  --set knobs.foo=bar \
  --set knobs.zeta=9

kubectl rollout status deploy/trainer --timeout=120s
kubectl wait --for=condition=Ready pod -l app=trainer --timeout=120s >/dev/null 2>&1 || true
pod_name="$(pick_trainer_pod)"
if [[ -z "$pod_name" ]]; then
  err "trainer pod not found"
fi

required_knobs=(
  "modekeeper/knob.alpha=1"
  "modekeeper/knob.foo=bar"
  "modekeeper/knob.zeta=9"
)

last_cycle=""
last_sorted=""

for _ in $(seq 1 30); do
  knob_lines=""
  while IFS= read -r candidate_pod; do
    [[ -n "$candidate_pod" ]] || continue
    current_knob_lines="$(trainer_knob_lines_for_pod "$candidate_pod" || true)"
    if [[ -n "$current_knob_lines" ]]; then
      pod_name="$candidate_pod"
      knob_lines="$current_knob_lines"
      break
    fi
  done < <(list_trainer_pods)

  if [[ -n "$knob_lines" ]]; then
    first_knob_line=""
    cycle=""
    saw_repeat=0
    while IFS= read -r knob_line; do
      if [[ -z "$first_knob_line" ]]; then
        first_knob_line="$knob_line"
        cycle="$knob_line"
        continue
      fi

      if [[ "$knob_line" == "$first_knob_line" ]]; then
        saw_repeat=1
        break
      fi

      cycle+=$'\n'"$knob_line"
    done <<< "$knob_lines"

    sorted_cycle="$(printf "%s\n" "$cycle" | LC_ALL=C sort)"

    last_cycle="$cycle"
    last_sorted="$sorted_cycle"

    if [[ "$saw_repeat" -ne 1 ]]; then
      sleep 2
      continue
    fi

    missing_required=0
    for required in "${required_knobs[@]}"; do
      if ! printf "%s\n" "$cycle" | grep -Fxq "$required"; then
        missing_required=1
        break
      fi
    done

    if [[ "$missing_required" -eq 0 && "$cycle" == "$sorted_cycle" ]]; then
      echo "PASS: e2e trainer chart (kind) - knob log lines observed"
      exit 0
    fi
  fi

  sleep 2
done

echo "---- trainer logs ----"
found_pods=0
while IFS= read -r trainer_pod; do
  [[ -n "$trainer_pod" ]] || continue
  found_pods=1
  echo "-- $trainer_pod (current) --"
  kubectl logs "$trainer_pod" -c trainer --tail=200 || true
  echo "-- $trainer_pod (previous) --"
  kubectl logs "$trainer_pod" -c trainer --previous --tail=200 || true
done < <(list_trainer_pods)
if [[ "$found_pods" -eq 0 ]]; then
  kubectl get pods -l app=trainer -o wide || true
fi
echo "---- first knob cycle ----"
if [[ -n "$last_cycle" ]]; then
  printf "%s\n" "$last_cycle"
else
  echo "(no modekeeper/knob lines found)"
fi
echo "---- sorted first knob cycle ----"
if [[ -n "$last_sorted" ]]; then
  printf "%s\n" "$last_sorted"
else
  echo "(no modekeeper/knob lines found)"
fi
err "expected required sorted knob lines not found in first cycle"
