# Release Process (public showroom)

This is the canonical public release sequence.

## 1) Version bump + changelog in PR

Prepare a PR that includes:
- version bump in `pyproject.toml` (`[project].version`)
- changelog update for that version/date in `CHANGELOG.md`

Reliable version check from source (no installed package required):

```bash
python3 - <<'PY'
import tomllib
from pathlib import Path
print(tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))["project"]["version"])
PY
```

Optional installed-package check (only where package is installed):

```bash
python3 -c 'import importlib.metadata as m; print(m.version("modekeeper"))'
```

## 2) Merge PR to `main`

After review and CI pass, merge the PR and ensure local `main` is current.

## 3) Run release script on `main`

From repo root:

```bash
./scripts/release_public.sh
```

For CI/local smoke (checks + build only, no publish side effects):

```bash
./scripts/release_public.sh --dry-run
```

The script enforces:
- clean git working tree
- current branch is `main`
- local `main` matches `origin/main`
- version read from `pyproject.toml`
- tag does not already exist (local/remote)
- `python3 -m pip install -e .` and path-based test selection against latest `v*` tag
  - docs-only changes (`docs/**`): skip pytest
  - scripts-only changes (`bin/**`, `scripts/**`): run smoke set
    - `tests/test_cli_version.py`
    - `tests/test_cli_doctor.py`
    - `tests/test_cli_quickstart.py`
    - `tests/test_mk097_export_bundle.py`
  - code changes (`src/**`, `tests/**`, `pyproject.toml`, `.github/workflows/**`, or any other path): run full `pytest -q`
  - overrides: `MK_RELEASE_FULL=1` forces full pytest, `MK_RELEASE_SMOKE=1` forces smoke set
- procurement pack generation (`./bin/mk-procurement-pack`)
- annotated tag creation and push
- GitHub Release creation with assets:
  - `report/procurement_pack/procurement_pack.tar.gz`
  - `report/procurement_pack/checksums.sha256`

With `--dry-run`, the script stops after verifying procurement pack assets and prints `dry-run ok` with the computed tag and asset paths.

## Do not commit generated outputs

Do not commit release artifacts under `report/**`.
Release assets are attached to the GitHub Release instead.
