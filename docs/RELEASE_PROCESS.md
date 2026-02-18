# Release Process (public repository)

This document defines the canonical release sequence for the public package.

## 1) Version bump

Update version in all required files:
- `pyproject.toml` (`[project].version`)
- `src/modekeeper/__init__.py` (`__version__`)
- `CHANGELOG.md` (new section for target version/date)

## 2) Pre-PR checks

```bash
python -m pip install -e .[dev]
pytest -q
PYTHONPATH=src python -m modekeeper.cli --version
PYTHONPATH=src python -m modekeeper.cli --help
```

Optional but recommended:
```bash
./bin/mk-procurement-pack
```

## 3) PR stage
- Open PR with only intended release changes.
- Ensure CI is green.
- Confirm no logic drift outside release scope.

## 4) Merge to main
- Merge PR after review and CI pass.
- Pull latest `main` locally before publishing.

## 5) Publish (wheel-only)

Canonical command:
```bash
bin/mk-release-stub
```

What the script enforces:
- builds wheel only (`python -m build --wheel`)
- rejects sdist in `dist/`
- requires exactly one wheel in `dist/`
- runs `twine check`
- audits wheel contents for forbidden paths (`tests/`, `.git`, `modekeeper_pro`, and denylist entries)
- uploads wheel via `twine upload dist/*.whl`

## 6) Post-publish smoke

Run both smoke paths (fresh environments), then tag.

### mk-install path
```bash
rm -rf /tmp/mk-install-smoke-home
HOME=/tmp/mk-install-smoke-home bash ./bin/mk-install
/tmp/mk-install-smoke-home/.modekeeper/venv/bin/python -c 'import importlib.metadata as m; print(m.version(\"modekeeper\"))'
```

### pip path
```bash
rm -rf /tmp/mk-pip-smoke-venv
python -m venv /tmp/mk-pip-smoke-venv
PIP_DISABLE_PIP_VERSION_CHECK=1 /tmp/mk-pip-smoke-venv/bin/pip install -U --no-cache-dir --index-url https://pypi.org/simple modekeeper
/tmp/mk-pip-smoke-venv/bin/python -c 'import importlib.metadata as m; print(m.version(\"modekeeper\"))'
```

## 7) Tag and release

Only after smoke success:
```bash
git tag -a vX.Y.Z -m "release vX.Y.Z"
git push origin vX.Y.Z
```

Then create GitHub release notes referencing changelog section.

## Do not commit
- `report/**`
- `dist/**`
- `build/**`
- `*.egg-info/**`
- local secrets (e.g. `secrets/**`, local license/key material)
- temporary local env artifacts (`.venv/**`, `.pytest_cache/**`)

## Final release checklist
- version aligned in `pyproject.toml` and `src/modekeeper/__init__.py`
- changelog updated
- tests pass
- wheel-only publish done via `bin/mk-release-stub`
- smoke checks passed
- tag created after smoke
