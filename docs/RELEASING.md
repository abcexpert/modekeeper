# Releasing (One Button)

## Related docs
- `docs/HANDOFF.md` - customer handoff flow and verify/export steps.
- `docs/SNAPSHOT.md` - canonical customer-managed execution model and status context.

Run releases from WSL2 in the public repo checkout:

- Public repo: `~/code/modekeeper`
- Private repo: `~/code/modekeeper-private`

## Prerequisites

- `gh` authenticated: `gh auth login`
- Remotes named `github` in both repos:
  - public: `abcexpert/modekeeper`
  - private: `abcexpert/modekeeper-private`
- Both repos have `main` checked out and clean worktrees before running.

## Command

From `~/code/modekeeper`:

```bash
./scripts/mk-release-all.sh
```

The script will:

- enforce clean `main` and hard-reset to `<remote>/main` for both repos
- create/push annotated tags
- create missing GitHub releases with `--generate-notes`
- wait for PyPI wheel visibility, then validate install/version consistency
- sync private `pyproject.toml` version to public when needed, then tag/release private

## Customer-managed execution note

Release automation is vendor-side packaging only. Customer runtime execution remains self-serve and read-only:

- customer-managed read-only k8s runner
- runner executes `mk quickstart --out /out/quickstart`
- artifacts are collected via `kubectl cp ...:/out/quickstart`
- local workstation builds `mk export handoff-pack`
- `bash HANDOFF_VERIFY.sh` is the verify step
- read-only verify patch denial (`top_blocker=rbac_denied`) is a non-blocking note in this self-serve flow

## PyPI note

Publishing to PyPI automatically creates the release entry in:
`https://pypi.org/manage/project/modekeeper/releases/`

No separate PyPI UI release-creation step is required.
