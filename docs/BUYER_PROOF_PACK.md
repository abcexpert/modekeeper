# Buyer Proof Pack

## Purpose

Buyer Proof Pack is a one-command, customer-safe evidence run for enterprise review. It produces auditable read-only artifacts that Security and Procurement can inspect for verify outcomes, safety gates, and workflow traceability.

## Run this

```bash
./bin/mk-buyer-pack
```

This writes artifacts to `report/buyer_pack`.

## What is already proven (public, replayable)

- Public core behavior is frozen at `v0.1.33`.
- On current `main`, replayable proof tranche passes 3/3 published matrix scenarios:
  - `replica_overprovisioning`
  - `cpu_pressure`
  - `memory_pressure`
- Replay command:

```bash
scripts/proof-matrix-replay.sh
```

## What to hand to Security / Procurement

Share the generated evidence directory:

- `report/buyer_pack/**`

Key artifact locations:

- `report/buyer_pack/plan/` (quickstart dry-run planning evidence)
- `report/buyer_pack/verify/` (verify report evidence)
- `report/buyer_pack/export/` (exported bundle artifacts)
- `report/buyer_pack/dryrun/` (additional closed-loop dry-run evidence, including decision trace/explain artifacts)

## Checklist (what to verify)

- Verify gate outcome is recorded:
  - check `report/buyer_pack/plan/closed_loop_latest.json` (`verify_ok`)
  - check `report/buyer_pack/verify/k8s_verify_latest.json` (`ok` and `verify_blocker`)
- Kill-switch gate is visible in plan evidence:
  - check `report/buyer_pack/plan/closed_loop_latest.json` (`kill_switch_active`)
  - gate behavior reference: `docs/WORKFLOW.md`
- License gate is visible in plan evidence:
  - check `report/buyer_pack/plan/closed_loop_latest.json` (`entitlements_summary`, `apply_blocked_reason`)
  - gate behavior reference: `docs/WORKFLOW.md`

For public/private boundary and distribution controls, use `docs/DISTRIBUTION_POLICY.md`.

## First-contact claim boundary

Justified:
- Verify-first strict read-only assessment workflow (`observe -> plan -> verify -> export`).
- Customer-managed runtime boundary.
- Gated/separate apply path (not baseline public evaluation).
- Reproducible replay evidence for the published 3-scenario matrix.

Not justified:
- Universal/exhaustive workload/environment coverage.
- Guaranteed savings or guaranteed risk reduction outcomes.
- Vendor-operated/autonomous production execution.
- Public apply/implementation availability.
