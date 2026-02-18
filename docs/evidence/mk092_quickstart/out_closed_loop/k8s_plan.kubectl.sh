#!/usr/bin/env bash
set -Eeuo pipefail
# Plan-only: not executed by ModeKeeper
echo "ModeKeeper K8s plan-only script (NOT executed automatically). Review before running." >&2
echo "Target: namespace=default deployment=trainer" >&2
echo "Current kubectl context:" >&2
kubectl config current-context >&2 || true

kubectl -n default patch deployment/trainer --type merge -p '{"metadata": {"annotations": {"modekeeper/knob.microbatch_size": "16"}}, "spec": {"template": {"metadata": {"annotations": {"modekeeper/knob.microbatch_size": "16"}}}}}'
