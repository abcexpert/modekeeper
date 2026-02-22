#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'

on_err() {
  local exit_code=$?
  local line_no=${1:-unknown}
  local cmd=${2:-unknown}
  echo "ERROR: command failed (exit ${exit_code}) at line ${line_no}: ${cmd}" >&2
  exit "${exit_code}"
}

cleanup() {
  if [[ -n "${TMPDIR_VENV:-}" && -d "${TMPDIR_VENV}" ]]; then
    rm -rf "${TMPDIR_VENV}" || true
  fi
}

trap cleanup EXIT
trap 'on_err "${LINENO}" "${BASH_COMMAND}"' ERR

log() {
  echo "[$(date +%H:%M:%S)] $*"
}

die() {
  echo "ERROR: $*" >&2
  exit 1
}

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "required command not found in PATH: $1"
}

need_cmd git
need_cmd gh
need_cmd python3

PUB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PRIV_DIR="${PRIV_DIR:-$HOME/code/modekeeper-private}"

PUB_REMOTE="${PUB_REMOTE:-github}"
PRIV_REMOTE="${PRIV_REMOTE:-github}"

PUB_REPO="${PUB_REPO:-abcexpert/modekeeper}"
PRIV_REPO="${PRIV_REPO:-abcexpert/modekeeper-private}"
PYPI_NAME="${PYPI_NAME:-modekeeper}"

[[ -d "${PRIV_DIR}" ]] || die "private repo path does not exist: ${PRIV_DIR}"

gh auth status -h github.com >/dev/null 2>&1 || die "gh is not authenticated; run: gh auth login"

read_pyproject_version() {
  local pyproject_path="$1"
  python3 - "$pyproject_path" <<'PY'
from pathlib import Path
import sys
import tomllib

path = Path(sys.argv[1])
if not path.exists():
    raise SystemExit(f"pyproject.toml not found: {path}")

obj = tomllib.loads(path.read_text(encoding="utf-8"))
version = ((obj.get("project") or {}).get("version") or "").strip()
if not version:
    raise SystemExit(f"project.version is missing in {path}")
print(version)
PY
}

ensure_repo_ready() {
  local dir="$1"
  local remote="$2"
  local label="$3"

  [[ -d "${dir}/.git" ]] || die "${label}: not a git repository: ${dir}"

  cd "$dir"

  git remote get-url "$remote" >/dev/null 2>&1 || die "${label}: missing remote '${remote}'"

  local branch
  branch="$(git rev-parse --abbrev-ref HEAD)"
  [[ "$branch" == "main" ]] || die "${label}: expected current branch 'main', got '${branch}'"

  if [[ -n "$(git status --porcelain)" ]]; then
    die "${label}: working tree is not clean"
  fi

  log "${label}: fetching ${remote} (branches + tags)"
  git fetch "$remote" --prune --tags --force >/dev/null

  git rev-parse --verify "${remote}/main" >/dev/null 2>&1 || die "${label}: cannot resolve ${remote}/main"

  log "${label}: resetting hard to ${remote}/main"
  git reset --hard "${remote}/main" >/dev/null

  if [[ -n "$(git status --porcelain)" ]]; then
    die "${label}: repository became dirty after reset"
  fi
}

refuse_if_tag_exists() {
  local dir="$1"
  local remote="$2"
  local tag="$3"
  local label="$4"

  cd "$dir"

  if git rev-parse -q --verify "refs/tags/${tag}" >/dev/null 2>&1; then
    die "${label}: local tag already exists: ${tag}"
  fi

  if git ls-remote --exit-code --tags "$remote" "refs/tags/${tag}" >/dev/null 2>&1; then
    die "${label}: remote tag already exists on '${remote}': ${tag}"
  fi
}

create_tag_and_release() {
  local dir="$1"
  local remote="$2"
  local repo="$3"
  local tag="$4"
  local title="$5"

  cd "$dir"

  log "${repo}: creating annotated tag ${tag}"
  git tag -a "$tag" -m "$title"

  log "${repo}: pushing tag ${tag} to ${remote}"
  git push "$remote" "refs/tags/${tag}"

  if gh release view "$tag" -R "$repo" >/dev/null 2>&1; then
    log "${repo}: GitHub release already exists for ${tag}; skipping create"
  else
    log "${repo}: creating GitHub release ${tag} with generated notes"
    gh release create "$tag" -R "$repo" --generate-notes >/dev/null
  fi
}

wait_for_pypi_wheel() {
  local package_name="$1"
  local version="$2"

  log "PyPI: waiting for ${package_name}==${version} to appear in JSON and simple index (wheel only)"

  python3 - "$package_name" "$version" <<'PY'
import json
import sys
import time
import urllib.request as req
from urllib.error import HTTPError, URLError

name = sys.argv[1]
ver = sys.argv[2]

timeout_seconds = 420
poll_seconds = 5

def fetch_json():
    url = f"https://pypi.org/pypi/{name}/{ver}/json?cb={int(time.time())}"
    with req.urlopen(url, timeout=20) as r:
        payload = json.load(r)
    filenames = [u.get("filename", "") for u in payload.get("urls", [])]
    wheels = [f for f in filenames if f.endswith(".whl")]
    return wheels

def fetch_simple():
    url = f"https://pypi.org/simple/{name}/?cb={int(time.time())}"
    with req.urlopen(url, timeout=20) as r:
        return r.read().decode("utf-8", "replace")

deadline = time.time() + timeout_seconds
last_error = None

while time.time() < deadline:
    try:
        wheels = fetch_json()
        simple_html = fetch_simple()

        if wheels and any(wheel in simple_html for wheel in wheels):
            print("OK: PyPI JSON and simple index contain the new wheel(s):")
            for wheel in wheels:
                print(f" - {wheel}")
            raise SystemExit(0)

        print("WAIT: release not fully visible yet")
    except (HTTPError, URLError, TimeoutError, ValueError) as exc:
        last_error = repr(exc)
        print(f"WAIT: transient PyPI lookup error: {last_error}")

    time.sleep(poll_seconds)

print("ERROR: timed out waiting for wheel visibility in PyPI JSON + simple index")
if last_error:
    print(f"Last lookup error: {last_error}")
raise SystemExit(1)
PY
}

validate_install_and_versions() {
  local package_name="$1"
  local version="$2"

  TMPDIR_VENV="$(mktemp -d)"

  log "Validation: creating fresh venv at ${TMPDIR_VENV}"
  python3 -m venv "${TMPDIR_VENV}/venv"

  log "Validation: installing ${package_name}==${version} with --no-cache-dir"
  "${TMPDIR_VENV}/venv/bin/pip" -q install -U pip
  "${TMPDIR_VENV}/venv/bin/pip" -q install --no-cache-dir "${package_name}==${version}"

  log "Validation: checking module __version__ equals importlib.metadata version"
  "${TMPDIR_VENV}/venv/bin/python" - "$package_name" <<'PY'
import importlib
import importlib.metadata as metadata
import sys

name = sys.argv[1]
module = importlib.import_module(name)
dist_ver = metadata.version(name)
pkg_ver = getattr(module, "__version__", None)

if pkg_ver is None:
    raise SystemExit(f"{name}.__version__ is missing")

print(f"dist version: {dist_ver}")
print(f"module __version__: {pkg_ver}")

if dist_ver != pkg_ver:
    raise SystemExit(f"version mismatch: dist={dist_ver} module={pkg_ver}")
PY

  log "Validation: install/version check passed"
}

sync_private_version_if_needed() {
  local dir="$1"
  local remote="$2"
  local target_version="$3"

  cd "$dir"

  local current_version
  current_version="$(read_pyproject_version "${dir}/pyproject.toml")"
  log "Private version: ${current_version}; public version: ${target_version}"

  if [[ "${current_version}" == "${target_version}" ]]; then
    log "Private version already matches public"
    return 0
  fi

  log "Private version differs; updating pyproject.toml to ${target_version}"

  python3 - "${dir}/pyproject.toml" "${target_version}" <<'PY'
from pathlib import Path
import re
import sys

path = Path(sys.argv[1])
new_version = sys.argv[2]
text = path.read_text(encoding="utf-8")
updated, count = re.subn(
    r'(?m)^(version\s*=\s*")[^"]+("\s*)$',
    rf'\g<1>{new_version}\2',
    text,
    count=1,
)
if count != 1:
    raise SystemExit(f"failed to update version in {path}")
path.write_text(updated, encoding="utf-8")
print(f"Updated {path} to version {new_version}")
PY

  git add pyproject.toml
  git diff --cached --quiet && die "private version update produced no staged diff"

  git commit -m "release: v${target_version} (sync version with public)" >/dev/null
  git push "$remote" main >/dev/null

  log "Private main updated and pushed"
}

log "PUBLIC: ${PUB_REPO}"
ensure_repo_ready "$PUB_DIR" "$PUB_REMOTE" "public"

PUB_VERSION="$(read_pyproject_version "${PUB_DIR}/pyproject.toml")"
[[ -n "$PUB_VERSION" ]] || die "public version is empty"
TAG="v${PUB_VERSION}"
log "Public version=${PUB_VERSION}, tag=${TAG}"

refuse_if_tag_exists "$PUB_DIR" "$PUB_REMOTE" "$TAG" "public"
create_tag_and_release "$PUB_DIR" "$PUB_REMOTE" "$PUB_REPO" "$TAG" "release: ${TAG}"

wait_for_pypi_wheel "$PYPI_NAME" "$PUB_VERSION"
validate_install_and_versions "$PYPI_NAME" "$PUB_VERSION"

log "PRIVATE: ${PRIV_REPO}"
ensure_repo_ready "$PRIV_DIR" "$PRIV_REMOTE" "private"
sync_private_version_if_needed "$PRIV_DIR" "$PRIV_REMOTE" "$PUB_VERSION"

refuse_if_tag_exists "$PRIV_DIR" "$PRIV_REMOTE" "$TAG" "private"
create_tag_and_release "$PRIV_DIR" "$PRIV_REMOTE" "$PRIV_REPO" "$TAG" "release: ${TAG} (sync with public)"

log "DONE: release flow completed for ${TAG}"
