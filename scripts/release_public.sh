#!/usr/bin/env bash
set -Eeuo pipefail

on_err() {
  local exit_code=$?
  local line_no=${1:-unknown}
  echo "ERROR: release failed at line ${line_no} (exit ${exit_code})" >&2
}

on_signal() {
  local sig="$1"
  echo "ERROR: interrupted by ${sig}" >&2
  exit 130
}

trap 'on_err $LINENO' ERR
trap 'on_signal INT' INT
trap 'on_signal TERM' TERM

if [[ "$(pwd)" != "$(git rev-parse --show-toplevel 2>/dev/null || true)" ]]; then
  echo "ERROR: run this script from the repository root." >&2
  exit 1
fi

if [[ ! -f "pyproject.toml" ]] || [[ ! -d ".git" ]]; then
  echo "ERROR: repository root checks failed (pyproject.toml/.git missing)." >&2
  exit 1
fi

if [[ -n "$(git status --porcelain)" ]]; then
  echo "ERROR: git working tree is not clean." >&2
  git status --short >&2
  exit 1
fi

branch="$(git branch --show-current)"
if [[ "${branch}" != "main" ]]; then
  echo "ERROR: current branch must be main (got: ${branch})." >&2
  exit 1
fi

echo "Fetching origin/main..."
git fetch origin main --tags

local_main_sha="$(git rev-parse main)"
origin_main_sha="$(git rev-parse origin/main)"

if [[ "${local_main_sha}" != "${origin_main_sha}" ]]; then
  echo "ERROR: local main is not up-to-date with origin/main." >&2
  echo "local main : ${local_main_sha}" >&2
  echo "origin/main: ${origin_main_sha}" >&2
  exit 1
fi

version="$(python3 - <<'PY'
import tomllib
from pathlib import Path

pyproject = Path("pyproject.toml")
data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
print(data["project"]["version"])
PY
)"

if [[ -z "${version}" ]]; then
  echo "ERROR: failed to read version from pyproject.toml." >&2
  exit 1
fi

TAG="v${version}"
RELEASE_TITLE="${TAG}"
RELEASE_NOTES="Public showroom release ${TAG}"
PACK_DIR="report/procurement_pack"
PACK_TARBALL="${PACK_DIR}/procurement_pack.tar.gz"
PACK_CHECKSUMS="${PACK_DIR}/checksums.sha256"

if git rev-parse --verify --quiet "refs/tags/${TAG}" >/dev/null; then
  echo "ERROR: tag already exists locally: ${TAG}" >&2
  exit 1
fi

if git ls-remote --exit-code --tags origin "refs/tags/${TAG}" >/dev/null 2>&1; then
  echo "ERROR: tag already exists on origin: ${TAG}" >&2
  exit 1
fi

echo "Installing package in editable mode..."
python3 -m pip install -e .

echo "Running tests..."
pytest -q

echo "Building procurement pack..."
./bin/mk-procurement-pack

if [[ ! -f "${PACK_TARBALL}" ]]; then
  echo "ERROR: expected release asset not found: ${PACK_TARBALL}" >&2
  exit 1
fi

if [[ ! -f "${PACK_CHECKSUMS}" ]]; then
  echo "ERROR: expected release asset not found: ${PACK_CHECKSUMS}" >&2
  exit 1
fi

echo "Creating annotated tag ${TAG} on HEAD..."
git tag -a "${TAG}" -m "release ${TAG}"

echo "Pushing main..."
git push origin main

echo "Pushing tag ${TAG}..."
git push origin "${TAG}"

echo "Creating GitHub release ${TAG}..."
release_output="$(gh release create "${TAG}" "${PACK_TARBALL}" "${PACK_CHECKSUMS}" --title "${RELEASE_TITLE}" --notes "${RELEASE_NOTES}" 2>&1)"

echo "${release_output}"
release_url="$(printf '%s\n' "${release_output}" | rg -m1 -o 'https://[^[:space:]]+' || true)"

if [[ -z "${release_url}" ]]; then
  repo_url="$(git remote get-url origin)"
  repo_url="${repo_url%.git}"
  if [[ "${repo_url}" =~ ^git@github.com:(.+)$ ]]; then
    repo_url="https://github.com/${BASH_REMATCH[1]}"
  fi
  if [[ "${repo_url}" =~ ^https://github.com/.+ ]]; then
    release_url="${repo_url}/releases/tag/${TAG}"
  fi
fi

echo
echo "Release succeeded"
echo "Tag: ${TAG}"
if [[ -n "${release_url}" ]]; then
  echo "Release URL: ${release_url}"
fi
echo "Assets: ${PACK_TARBALL}, ${PACK_CHECKSUMS}"
