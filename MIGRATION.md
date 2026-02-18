# Public Snapshot Migration

## Included

- Public `modekeeper` package sources under `src/`.
- Public operator scripts including `bin/mk-install`, `bin/mk-buyer-pack`, `bin/mk-procurement-pack`, and `bin/mk-enterprise-eval`.
- Link-first docs and buyer/procurement references under `docs/`.
- Public CI checks in `.github/workflows/ci.yml` including boundary guard.

## Excluded

- `packages/<private_package>/**`.
- License-gate assets (`tools/*license-gate*`).
- Systemd unit templates under `tools/systemd/`.
- Pro-dependent tests/scripts removed from this snapshot.

## Generate Procurement Pack

From repo root:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -U pip
.venv/bin/python -m pip install -e .
./bin/mk-procurement-pack
```

Primary outputs:
- `report/procurement_pack/procurement_pack.tar.gz`
- `report/procurement_pack/checksums.sha256`
- `report/procurement_pack/buyer_pack/`
