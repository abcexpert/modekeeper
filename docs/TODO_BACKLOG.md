# TODO / FIXME / HACK Backlog

Source scan command:
```bash
rg -n --hidden -S "\b(TODO|FIXME|HACK)\b|\b(todo|fixme|hack)\b" . --glob '!.git/**'
```

Scan date: 2026-02-18

## docs
- `docs/PROJECT_MAP.md:61`
  - `MK-112` (TODO): PyPI landing README + enterprise quickstart.
- `docs/TICKETS.md:479`
  - TODO tickets for real-cluster/GPU work.

## cli
- No TODO/FIXME/HACK markers found.

## tests
- No TODO/FIXME/HACK markers found.

## build
- No TODO/FIXME/HACK markers found.

## security
- No TODO/FIXME/HACK markers found.

## Notes
- `.git/` history also contains historical commit messages with "TODO"; those are intentionally excluded from actionable backlog.
