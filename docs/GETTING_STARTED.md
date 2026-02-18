# ModeKeeper Quickstart (public stub)

## Install

```bash
python -m pip install -U modekeeper
```

Or use repo artifact metadata:

```bash
export MODEKEEPER_REPO_BASE_URL="https://<repo-base-url>"
./bin/mk-install
```

## First commands

```bash
mk --help
mk observe --source synthetic --duration 10s --out report/getting_started/observe
mk closed-loop run --scenario drift --observe-source synthetic --observe-duration 10s --dry-run --out report/getting_started/plan
```

## Notes

- Public snapshot is link-first and safe-by-default (observe/plan/verify-first flow).
- Apply/mutate paths remain gated behavior and are not part of this public stub snapshot.
- Procurement artifacts are generated via `./bin/mk-procurement-pack`.
