# Record/Replay Playbook (k8s observe -> file replay)

This is the primary dev/debug workflow when you do not have a GPU available.

## Record from k8s

1. Capture a short observe trace from your training workload:

```bash
mk observe --source k8s \
  --k8s-namespace <ns> \
  --k8s-deployment <deployment> \
  --container <container> \
  --duration 30s \
  --out report/observe_capture
```

2. The observe report is saved as `report/observe_capture/observe_latest.json`
   (summary JSON) plus `report/observe_capture/explain.jsonl`.
3. To record the raw observe stream as JSONL, add `--record-raw /path/to/observe.jsonl`.
   Replay the same file with `--observe-source file --observe-path /path/to/observe.jsonl`.
4. For replay, capture the same JSONL log stream your workload emits (the input
   to `--source k8s`) into a file (for example via `kubectl logs ... > observe.jsonl`),
   then use that JSONL file as the `--observe-path`.

## Replay in closed-loop (file source)

Use the recorded JSONL as input to the closed-loop pipeline without hitting k8s:

```bash
mk closed-loop run --scenario drift --dry-run \
  --observe-source file \
  --observe-path /path/to/observe.jsonl \
  --out report/replay_run
```

For multi-iteration playback:

```bash
mk closed-loop watch --scenario drift --dry-run \
  --observe-source file \
  --observe-path /path/to/observe.jsonl \
  --max-iterations 3 --interval 0s \
  --out report/replay_watch
```

## Synthetic replay example (file source)

Synthetic incident: latency burst + loss drift (file replay).

Captured artifacts:
- Raw observe JSONL: `docs/evidence/mk060/observe_raw.jsonl`
- Replay output: `docs/evidence/mk060/replay_run/` (summary + reports)

Reproduce the replay:

```bash
mk closed-loop run --scenario drift --dry-run \
  --observe-source file \
  --observe-path docs/evidence/mk060/observe_raw.jsonl \
  --out docs/evidence/mk060/replay_run
```

Expected outcome:
- `summary.md` shows proposed actions (dry-run) and `k8s_plan_items: 4`
- `closed_loop_latest.json` contains `signals` with `drift=true` and `burst=true`

## Real incident playbook: RBAC patch denied (MK-055)

Evidence:
- Plan: `docs/evidence/mk055/k8s_plan.json`
- Verify report: `docs/evidence/mk055/k8s_verify_latest.json`

One-command replay (idempotent):
- `docs/evidence/mk060/rbac_replay/setup.sh`
- `docs/evidence/mk060/rbac_replay/cleanup.sh`

Manual steps (if you prefer to run by hand):

1. Apply RBAC fixture (namespace, deployment, serviceaccount, role, rolebinding):

```bash
kubectl apply -f docs/evidence/mk060/rbac_replay/fixture.yaml
```

2. Add ClusterRole + ClusterRoleBinding for get namespaces:

```bash
kubectl apply -f docs/evidence/mk060/rbac_replay/ns_get_rbac.yaml
```

3. Create token and kubeconfig (insecure-skip-tls-verify=true):

```bash
SA_TOKEN=$(kubectl -n mk055-rbac-deny create token mk055-no-patch)
APISERVER=$(kubectl config view --minify -o jsonpath='{.clusters[0].cluster.server}')
cat > docs/evidence/mk060/rbac_replay/kubeconfig.mk055 <<EOF
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
EOF
```

4. Run verify against the plan:

```bash
KUBECONFIG=docs/evidence/mk060/rbac_replay/kubeconfig.mk055 \
  mk k8s verify --plan docs/evidence/mk055/k8s_plan.json \
  --out report/mk060_rbac_replay
```

Expected outcome:
- `verify_blocker.kind=rbac_denied`
- `auth_can_i_get_deployments_by_namespace.mk055-rbac-deny=true`
- `auth_can_i_patch_deployments_by_namespace.mk055-rbac-deny=false`

## Notes

- Record once from k8s, then iterate locally by replaying the JSONL through
  `closed-loop run` or `closed-loop watch`.
- This avoids GPU requirements while exercising the policy, planning, and
  reporting pipeline end-to-end.
- Replays tolerate dirty logs: blank lines, invalid JSON, wrong shapes, and
  missing fields are dropped without failing the run.
- Drop counters are exposed as `observe_ingest` in `closed_loop_latest.json`
  (and per-iteration closed-loop reports) plus the `closed_loop_observe_source`
  explain event payload.
