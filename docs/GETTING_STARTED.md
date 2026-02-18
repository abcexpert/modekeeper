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
mk --version
mk doctor
mk quickstart --observe-source synthetic
```

## Notes

- Public snapshot is link-first and safe-by-default (observe/plan/verify-first flow).
- Apply/mutate paths remain gated behavior and are not part of this public stub snapshot.
- Procurement artifacts are generated via `./bin/mk-procurement-pack`.
