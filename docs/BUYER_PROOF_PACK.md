# Buyer Proof Pack

## Purpose

Buyer Proof Pack is a one-command, customer-safe evidence run for enterprise review. It produces auditable read-only artifacts that Security and Procurement can inspect for safety gates, verification outcomes, and workflow traceability.

## Run this

```bash
./bin/mk-buyer-pack
```

This writes artifacts to `report/buyer_pack`.

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
