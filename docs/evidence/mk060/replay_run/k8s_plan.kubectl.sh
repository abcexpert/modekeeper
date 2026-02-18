#!/usr/bin/env bash
set -Eeuo pipefail
# Plan-only: not executed by ModeKeeper
echo "ModeKeeper K8s plan-only script (NOT executed automatically). Review before running." >&2
echo "Target: namespace=default deployment=trainer" >&2
echo "Current kubectl context:" >&2
kubectl config current-context >&2 || true

kubectl -n default patch deployment/trainer --type merge -p '{"metadata": {"annotations": {"modekeeper/knob.grad_accum_steps": "8"}}, "spec": {"template": {"metadata": {"annotations": {"modekeeper/knob.grad_accum_steps": "8"}}}}}'
kubectl -n default patch deployment/trainer --type merge -p '{"metadata": {"annotations": {"modekeeper/knob.microbatch_size": "32"}}, "spec": {"template": {"metadata": {"annotations": {"modekeeper/knob.microbatch_size": "32"}}}}}'
kubectl -n default patch deployment/trainer --type merge -p '{"metadata": {"annotations": {"modekeeper/knob.dataloader_prefetch_factor": "2"}}, "spec": {"template": {"metadata": {"annotations": {"modekeeper/knob.dataloader_prefetch_factor": "2"}}}}}'
kubectl -n default patch deployment/trainer --type merge -p '{"metadata": {"annotations": {"modekeeper/knob.concurrency": "4"}}, "spec": {"template": {"metadata": {"annotations": {"modekeeper/knob.concurrency": "4"}}}}}'
