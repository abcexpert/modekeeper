#!/usr/bin/env bash
set -Eeuo pipefail

cd "$(dirname "$0")/.."

./scripts/kind-bootstrap.sh
export DEV_SHELL_QUIET=1
source ./scripts/dev-shell.sh

out_dir="report/_smoke"
set +e
apply_output="$(
  MODEKEEPER_PAID=1 MODEKEEPER_KILL_SWITCH=1 \
    mk closed-loop run --scenario drift --apply --out "$out_dir" 2>&1
)"
apply_rc=$?
set -e

if [[ $apply_rc -eq 0 ]]; then
  echo "ERROR: apply unexpectedly succeeded while MODEKEEPER_KILL_SWITCH=1 was enabled" >&2
  printf '%s\n' "$apply_output" >&2
  exit 1
fi

if grep -Fq "MODEKEEPER_KILL_SWITCH=1 blocks apply/mutate operations" <<<"$apply_output"; then
  echo "OK: kill-switch enforced (expected)"
  exit 0
fi

echo "ERROR: mk closed-loop run failed with unexpected error" >&2
printf '%s\n' "$apply_output" >&2
exit "$apply_rc"
