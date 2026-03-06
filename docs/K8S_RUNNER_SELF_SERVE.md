# Self-Serve k8s Runner Runbook

Customer-managed runbook for read-only ModeKeeper runner lifecycle: install, collect artifacts, export/verify handoff, upgrade, rollback, uninstall.

## Scope and assumptions

- Customer-owned Kubernetes cluster and `kubectl` access.
- `mk` CLI is installed on the workstation where manifests/export are prepared.
- Runner image is available to the cluster runtime.
- Default runner command is read-only:
  - `mk quickstart --out /out/quickstart; echo MODEKEEPER_DONE; sleep 900`

## 1) Install

```bash
set -Eeuo pipefail

OUT=./report/install_k8s_runner
mk install k8s-runner --out "$OUT"

cd "$OUT"
./apply.sh
```

Operational checks:

```bash
NS=modekeeper-system
JOB=modekeeper-runner

kubectl -n "$NS" get job "$JOB"
kubectl -n "$NS" logs job/"$JOB" | tail -n 50
```

Primary success criterion (preferred):

```bash
kubectl -n "$NS" logs job/"$JOB" | grep -F "MODEKEEPER_DONE"
```

Secondary operational checks (optional, not primary):

```bash
kubectl -n "$NS" get job "$JOB" -o jsonpath='{.status.succeeded}'; echo
kubectl -n "$NS" get pods -l job-name="$JOB" -o wide
```

Note:
- Do not rely on `kubectl wait ... --for=jsonpath='{.status.phase}'=Running` as the main success signal for this Job.
- `MODEKEEPER_DONE` in logs is the reliable completion marker for the runner quickstart flow.

## 2) Local kind image note

If using local image preloaded into kind (`kind load docker-image ...`), generate manifests with:

```bash
mk install k8s-runner \
  --image modekeeper-runner:latest \
  --image-pull-policy Never \
  --out ./report/install_k8s_runner_local
```

Then apply:

```bash
cd ./report/install_k8s_runner_local
./apply.sh
```

## 3) Collect runner artifacts (`kubectl cp /out/quickstart`)

```bash
set -Eeuo pipefail

NS=modekeeper-system
JOB=modekeeper-runner
HOST_OUT=./out

mkdir -p "$HOST_OUT"
POD="$(kubectl -n "$NS" get pods -l job-name="$JOB" -o jsonpath='{.items[0].metadata.name}')"
kubectl -n "$NS" cp "$POD":/out/quickstart "$HOST_OUT/quickstart"
```

Expected minimum artifacts:

```bash
test -f "$HOST_OUT/quickstart/preflight/preflight_latest.json"
test -f "$HOST_OUT/quickstart/eval/eval_latest.json"
test -f "$HOST_OUT/quickstart/watch/watch_latest.json"
test -f "$HOST_OUT/quickstart/roi/roi_latest.json"
```

## 4) Build handoff-pack locally

```bash
set -Eeuo pipefail

mk export handoff-pack --in ./out/quickstart --out ./handoff
ls -1 ./handoff
```

Expected files:
- `handoff_pack.tar.gz`
- `handoff_manifest.json`
- `handoff_summary.md`
- `handoff_pack.checksums.sha256`
- `HANDOFF_VERIFY.sh`
- `README.md`

## 5) Verify handoff-pack

```bash
set -Eeuo pipefail

cd ./handoff
bash HANDOFF_VERIFY.sh
```

Success criterion: script prints `OK`.

Note:
- `top_blocker=rbac_denied` in quickstart artifacts is a read-only verify note and does not block handoff-pack verification.

## 6) Upgrade / update flow

Use a new output directory for each version/image and keep previous bundle for rollback.

```bash
set -Eeuo pipefail

NEW=./report/install_k8s_runner_vNEXT
mk install k8s-runner \
  --image modekeeper-runner:latest \
  --out "$NEW"

NS=modekeeper-system
JOB=modekeeper-runner

kubectl -n "$NS" delete job "$JOB" --ignore-not-found
( cd "$NEW" && ./apply.sh )
```

Post-update checks:

```bash
kubectl -n "$NS" get job "$JOB"
kubectl -n "$NS" logs job/"$JOB" | grep -F "MODEKEEPER_DONE"
kubectl -n "$NS" get job "$JOB" -o jsonpath='{.status.succeeded}'; echo
```

## 7) Rollback and uninstall

Rollback to previous known-good bundle:

```bash
set -Eeuo pipefail

NS=modekeeper-system
JOB=modekeeper-runner
PREV=./report/install_k8s_runner_vPREV

kubectl -n "$NS" delete job "$JOB" --ignore-not-found
( cd "$PREV" && ./apply.sh )
```

Uninstall:

```bash
set -Eeuo pipefail

cd ./report/install_k8s_runner
./rollback.sh
```

## 8) Air-gapped notes (brief)

- Build/package runner image in a connected environment, then transfer into the air-gapped registry/host using your approved transport.
- Validate image digest before use.
- Install `mk` and dependencies from internal package mirror or pre-approved wheelhouse.
- Run handoff verification fully offline on the target side:
  - `bash HANDOFF_VERIFY.sh` (requires `sha256sum` and `tar` only).
- Keep generated install bundles and handoff-pack artifacts in customer-controlled storage for audit and rollback.
