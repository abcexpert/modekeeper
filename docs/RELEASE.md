# Release

Distribution boundary policy for the public showroom snapshot is documented in `docs/DISTRIBUTION_POLICY.md`.

Public PyPI releases for `modekeeper` use:

```bash
bin/mk-release-stub
```

## Public release rules

1. Wheel-only uploads.
2. No manual wildcard uploads.
3. CI must run checks only.
4. Run install smoke checks before tagging.

## Smoke checks

```bash
rm -rf /tmp/mk-install-smoke-home
HOME=/tmp/mk-install-smoke-home bash ./bin/mk-install
/tmp/mk-install-smoke-home/.modekeeper/venv/bin/python -c 'import importlib.metadata as m; print(m.version(\"modekeeper\"))'
```

```bash
rm -rf /tmp/mk-pip-smoke-venv
python -m venv /tmp/mk-pip-smoke-venv
/tmp/mk-pip-smoke-venv/bin/pip install -U --no-cache-dir --index-url https://pypi.org/simple modekeeper
/tmp/mk-pip-smoke-venv/bin/python -c 'import importlib.metadata as m; print(m.version(\"modekeeper\"))'
```
