#!/usr/bin/env bash
set -Eeuo pipefail

cd "$(dirname "$0")/.."

./scripts/kind-bootstrap.sh
export DEV_SHELL_QUIET=1
source ./scripts/dev-shell.sh

out_dir="report/_smoke"
MODEKEEPER_PAID=1 MODEKEEPER_KILL_SWITCH=1 mk closed-loop run --scenario drift --apply --out "$out_dir"

report_path="$out_dir/closed_loop_latest.json"

jq -e '.schema_version == "v0"' "$report_path" >/dev/null
jq -e '.apply_requested == true' "$report_path" >/dev/null
jq -e '.apply_blocked_reason == "kill_switch"' "$report_path" >/dev/null

verify_path="$(jq -r '.k8s_verify_report_path' "$report_path")"
if [[ -z "$verify_path" || ! -f "$verify_path" ]]; then
  echo "ERROR: k8s_verify_report_path missing or not found: $verify_path" >&2
  exit 2
fi

jq -e '(.results | length) == (.proposed | length)' "$report_path" >/dev/null

echo "PASS: e2e smoke (kind) - kill switch blocked apply"
