#!/usr/bin/env bash
set -Eeuo pipefail

# paid-gate for e2e apply path
export MODEKEEPER_PAID="1"

NS="${NS:-default}"
DEPLOY="${DEPLOY:-trainer}"
OUT="${OUT:-report/_e2e_closed_loop_apply_k8s_gpu}"
DURATION="${DURATION:-10s}"
SIDECAR="${SIDECAR:-mk-telemetry}"

added=0

cleanup() {
  if [[ "$added" -eq 1 ]]; then
    echo "[cleanup] removing sidecar $SIDECAR from $NS/$DEPLOY"
    kubectl -n "$NS" get deploy "$DEPLOY" -o json | python -c 'import json,sys,pathlib; d=json.load(sys.stdin); cs=d["spec"]["template"]["spec"]["containers"]; idx=next((i for i,c in enumerate(cs) if c.get("name")=="'"$SIDECAR"'"), None); assert idx is not None, "sidecar not found"; p=pathlib.Path("/tmp/mk-telemetry-rm.json"); p.write_text(json.dumps([{"op":"remove","path":f"/spec/template/spec/containers/{idx}"}])+"\n", encoding="utf-8"); print(p)'
    kubectl -n "$NS" patch deployment "$DEPLOY" --type=json --patch-file /tmp/mk-telemetry-rm.json
    kubectl -n "$NS" rollout status "deploy/$DEPLOY" --timeout=180s
  fi
}
trap cleanup EXIT

echo "[check] deployment exists:"
kubectl -n "$NS" get deploy "$DEPLOY" -o name

echo "[check] current containers:"
kubectl -n "$NS" get deploy "$DEPLOY" -o jsonpath='{.spec.template.spec.containers[*].name}{"\n"}'

names="$(kubectl -n "$NS" get deploy "$DEPLOY" -o jsonpath='{.spec.template.spec.containers[*].name}')"
if echo " $names " | grep -q " $SIDECAR "; then
  echo "[info] sidecar already present: $SIDECAR"
else
  added=1
  cat > /tmp/mk-telemetry-add.json <<'JSON'
[
  {
    "op": "add",
    "path": "/spec/template/spec/containers/-",
    "value": {
      "name": "mk-telemetry",
      "image": "busybox:1.36",
      "command": ["sh", "-lc"],
      "args": [
        "while true; do ts=$(( $(date +%s) * 1000 )); echo '{\"ts\":'\"$ts\"',\"step_time_ms\":10,\"loss\":1.0,\"gpu_util_pct\":95,\"gpu_mem_util_pct\":92}'; sleep 1; done"
      ]
    }
  }
]
JSON
  sed -i "s/\"name\": \"mk-telemetry\"/\"name\": \"${SIDECAR}\"/g" /tmp/mk-telemetry-add.json
  echo "[apply] adding sidecar $SIDECAR to $NS/$DEPLOY"
  kubectl -n "$NS" patch deployment "$DEPLOY" --type=json --patch-file /tmp/mk-telemetry-add.json
  kubectl -n "$NS" rollout status "deploy/$DEPLOY" --timeout=180s
fi

echo "[check] before knob annotations (microbatch_size):"
kubectl -n "$NS" get deploy "$DEPLOY" -o jsonpath='{.metadata.annotations.modekeeper\/knob\.microbatch_size}{"\n"}' || true
kubectl -n "$NS" get deploy "$DEPLOY" -o jsonpath='{.spec.template.metadata.annotations.modekeeper\/knob\.microbatch_size}{"\n"}' || true

echo "[run] mk closed-loop run --apply (observe k8s logs, container=$SIDECAR) -> $OUT"
cd "$(dirname "$0")/.."
. .venv/bin/activate
mk closed-loop run --apply --k8s-namespace "$NS" --k8s-deployment "$DEPLOY" --observe-source k8s --observe-container "$SIDECAR" --observe-duration "$DURATION" --out "$OUT"

python - <<PY
import json
from pathlib import Path

out = Path("$OUT")
need = [
  "closed_loop_latest.json",
  "k8s_plan.json",
  "k8s_verify_latest.json",
  "k8s_apply_latest.json",
  "explain.jsonl",
  "summary.md",
]
missing = [n for n in need if not (out / n).exists()]
assert not missing, f"missing artifacts: {missing}"

cl = json.loads((out / "closed_loop_latest.json").read_text(encoding="utf-8"))
assert cl.get("apply_requested") is True, f"expected apply_requested=true, got {cl.get('apply_requested')}"
signals = (cl.get("signals") or {})
assert signals.get("gpu_saturated") is True, f"expected gpu_saturated=true, got {signals.get('gpu_saturated')}"

print("[ok] artifacts present; apply_requested=true; gpu_saturated=true")
PY

echo "[check] after knob annotations (microbatch_size):"
mb1="$(kubectl -n "$NS" get deploy "$DEPLOY" -o jsonpath='{.metadata.annotations.modekeeper\/knob\.microbatch_size}' || true)"
mb2="$(kubectl -n "$NS" get deploy "$DEPLOY" -o jsonpath='{.spec.template.metadata.annotations.modekeeper\/knob\.microbatch_size}' || true)"
echo "metadata microbatch_size=$mb1"
echo "template  microbatch_size=$mb2"

if [[ "$mb1" != "16" || "$mb2" != "16" ]]; then
  echo "[ERROR] expected microbatch_size annotation == 16 in both metadata and template"
  exit 2
fi

echo "[done] ok"
