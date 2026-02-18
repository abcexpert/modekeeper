# ModeKeeper — MVP v0 Definition of Done

## Scope
- MVP v0 covers plan-only closed-loop runs, k8s render/verify, and paid apply guarded by verify-ok and safety gates.
- Reports and artifacts follow the v0 report contract and are written deterministically.
- Documentation and smoke workflows are present for local and kind-based validation.

## Non-goals
- Multi-cluster orchestration or advanced scheduling.
- UI/dashboard, hosted service, or multi-tenant security model.
- Automatic remediation beyond the closed-loop apply path.

## Checklist
- [ ] Plan-only default: `mk closed-loop run` (no `--apply`) never mutates the cluster; it only writes plan/verify artifacts.
- [ ] `mk k8s render` and `mk k8s verify` accept a valid plan and write `*_latest.json` reports plus timestamped reports.
- [ ] Paid apply is gated: `MODEKEEPER_PAID=1` and `verify ok==true` are required, and `MODEKEEPER_KILL_SWITCH=1` blocks apply.
- [ ] Report contract holds for all generated reports: `schema_version == "v0"` and `duration_s` is an int.
- [ ] CLI contracts and workflows are documented in `docs/CLI_CONTRACTS.md` and `docs/WORKFLOW.md`.
- [ ] `pytest -q` passes in the repo environment.

## Acceptance smoke commands (kind)
- `./scripts/kind-bootstrap.sh`
- `./scripts/dev-shell.sh`
- `./scripts/e2e-smoke-kind.sh`
- `MODEKEEPER_PAID=1 MODEKEEPER_KILL_SWITCH=0 ./scripts/e2e-apply-kind.sh`
- `pytest -q`
