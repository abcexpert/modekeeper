# Releasing (One Button)

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

## PyPI note

Publishing to PyPI automatically creates the release entry in:
`https://pypi.org/manage/project/modekeeper/releases/`

No separate PyPI UI release-creation step is required.
