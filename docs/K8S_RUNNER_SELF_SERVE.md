# Customer-Managed Kubernetes Runner Runbook (Public)

Customer-managed runbook for a verify-first, read-only ModeKeeper runner lifecycle: install, collect artifacts, export/verify handoff, update, rollback, uninstall.

## Scope and assumptions

- Customer-owned Kubernetes cluster and `kubectl` access.
- `mk` CLI is installed where manifests and exports are prepared.
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

Primary success criterion:

```bash
kubectl -n "$NS" logs job/"$JOB" | grep -F "MODEKEEPER_DONE"
```

Optional secondary checks:

```bash
kubectl -n "$NS" get job "$JOB" -o jsonpath='{.status.succeeded}'; echo
kubectl -n "$NS" get pods -l job-name="$JOB" -o wide
```

## 2) Local kind image note

If using a locally preloaded image in kind (`kind load docker-image ...`):

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

## 4) Build handoff pack locally

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

## 5) Verify handoff pack

```bash
set -Eeuo pipefail

cd ./handoff
bash HANDOFF_VERIFY.sh
```

Success criterion: script prints `OK`.

Note:
- `top_blocker=rbac_denied` in quickstart artifacts is a read-only verify signal and does not block handoff-pack verification.

## 6) Update flow

Use a new output directory for each image/version and keep previous bundles for rollback.

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

Rollback to a previous known-good bundle:

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

## 8) Air-gapped notes

- Build/package the runner image in a connected environment, then transfer to your approved registry path.
- Validate image digest before use.
- Install `mk` and dependencies from an approved mirror or wheelhouse.
- Run handoff verification offline on the target side:
  - `bash HANDOFF_VERIFY.sh` (requires `sha256sum` and `tar` only).
- Keep install bundles and handoff artifacts in customer-controlled storage for audit and rollback.
