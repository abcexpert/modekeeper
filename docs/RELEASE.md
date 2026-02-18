# Release

Distribution boundary policy for the public showroom snapshot is documented in `docs/DISTRIBUTION_POLICY.md`.

## Canonical release command

Run from repo root on `main`:

```bash
./scripts/release_public.sh
```

The script validates branch/repo state, runs install + tests, generates the procurement pack, creates/pushes the release tag, and creates the GitHub Release with procurement assets.

## Public release rules

1. Version bump and changelog are prepared in a PR first.
2. Merge to `main` before release.
3. Run only `./scripts/release_public.sh` for public release.
4. Do not commit `report/**`; publish procurement artifacts as GitHub Release assets.

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
