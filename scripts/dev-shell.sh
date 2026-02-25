#!/usr/bin/env bash
set -Eeuo pipefail

this_file="${BASH_SOURCE[0]:-$0}"
this_dir="$(cd -- "$(dirname -- "$this_file")" && pwd -P)"

cd -- "$this_dir/.."

if [[ ! -d .venv ]]; then
  echo "ERROR: .venv not found (expected in repo root)" >&2
  exit 2
fi

# shellcheck disable=SC1091
source .venv/bin/activate

echo "OK: activated venv: $(python -V)"
echo "OK: mk: $(command -v mk)"
if [[ "${DEV_SHELL_QUIET:-0}" != "1" ]]; then
  mk --help | head -n 60
fi
