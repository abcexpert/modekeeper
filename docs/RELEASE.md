# Release

Distribution boundary policy for the public showroom snapshot is documented in `docs/DISTRIBUTION_POLICY.md`.

## Canonical release command

Run from repo root on `main`:

```bash
./scripts/release_public.sh
```

The script validates branch/repo state, runs install + tests, generates the procurement pack, creates/pushes the release tag, and creates the GitHub Release with procurement assets.
Test scope is selected from changed paths versus latest `v*` tag (fallback `origin/main`): docs-only skips pytest, scripts-only (`bin/**`, `scripts/**`) runs smoke tests, and code/other paths run full `pytest -q`. Use `MK_RELEASE_FULL=1` to force full pytest or `MK_RELEASE_SMOKE=1` to force smoke tests.

## Public release rules

1. Version bump and changelog are prepared in a PR first.
2. Merge to `main` before release.
3. Run only `./scripts/release_public.sh` for public release.
4. Do not commit `report/**`; publish procurement artifacts as GitHub Release assets.
5. Public PyPI release is wheel-only; no source distribution (`.tar.gz`) is allowed.
6. If an sdist is present on PyPI, delete the `.tar.gz` file from the PyPI project release UI.

## Version checks

Read version directly from source:

```bash
python3 - <<'PY'
import tomllib
from pathlib import Path
print(tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))["project"]["version"])
PY
```

Installed-package check (when installed):

```bash
python3 -c 'import importlib.metadata as m; print(m.version("modekeeper"))'
```
