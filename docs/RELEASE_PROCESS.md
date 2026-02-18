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

The script enforces:
- clean git working tree
- current branch is `main`
- local `main` matches `origin/main`
- version read from `pyproject.toml`
- tag does not already exist (local/remote)
- `python3 -m pip install -e .` and `pytest -q`
- procurement pack generation (`./bin/mk-procurement-pack`)
- annotated tag creation and push
- GitHub Release creation with assets:
  - `report/procurement_pack/procurement_pack.tar.gz`
  - `report/procurement_pack/checksums.sha256`

## Do not commit generated outputs

Do not commit release artifacts under `report/**`.
Release assets are attached to the GitHub Release instead.
