#!/usr/bin/env bash
set -Eeuo pipefail

NS="${NS:-default}"
DEPLOY="${DEPLOY:-trainer}"
OUT="${OUT:-report/_e2e_observe_k8s_gpu}"
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

echo "[run] mk observe from k8s logs (container=$SIDECAR) -> $OUT"
cd "$(dirname "$0")/.."
. .venv/bin/activate
mk observe --source k8s --k8s-namespace "$NS" --k8s-deployment "$DEPLOY" --container "$SIDECAR" --duration "$DURATION" --out "$OUT"

python - <<PY
import json
from pathlib import Path
p = Path("$OUT") / "observe_latest.json"
d = json.loads(p.read_text(encoding="utf-8"))
sc = d.get("sample_count", 0)
gpu = (d.get("signals") or {}).get("gpu_saturated")
assert sc > 0, f"expected sample_count>0, got {sc}"
assert gpu is True, f"expected gpu_saturated==true, got {gpu}"
print("[ok] sample_count=", sc, "gpu_saturated=", gpu, "file=", p)
PY

echo "[done] ok"
