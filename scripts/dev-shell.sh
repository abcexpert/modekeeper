#!/usr/bin/env bash
set -Eeuo pipefail

cd "$(dirname "$0")/.."

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
