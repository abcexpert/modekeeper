# OUTREACH_PACK

Compact first-contact outreach pack for ModeKeeper, aligned to current public snapshot and replayable proof tranche.

Scope: first contact only. No product-surface expansion claims.

## Source-of-truth boundaries

Use only these facts in first contact:
- Public core baseline is frozen at `v0.1.33`.
- Public core position is verify-first, strict read-only assessment for Kubernetes/GPU cost and risk.
- Canonical public flow is `observe -> plan -> verify -> export`.
- Runtime boundary is customer-managed execution in customer environments.
- Apply/mutate is separate, licensed, and gated (not baseline public evaluation).
- Replayable proof tranche on current `main` passes 3/3 via `scripts/proof-matrix-replay.sh`:
  - `replica_overprovisioning`
  - `cpu_pressure`
  - `memory_pressure`
- Replay evidence strengthens proof-layer rigor only; it does not widen public breadth.

Primary reference: `docs/SNAPSHOT.md`.

## 1) Cold opener (short)

Hi {{Name}} - ModeKeeper is a verify-first, strict read-only assessment for Kubernetes/GPU cost and risk.

Public core is frozen at `v0.1.33`; current replayable proof on `main` passes 3/3 published scenarios (`replica_overprovisioning`, `cpu_pressure`, `memory_pressure`).

If useful, we can do a short fit check for your read-only assessment scope before any apply discussion.

## 2) Follow-up after positive reply (short)

Great - for first contact we keep this narrow: read-only assessment only (`observe -> plan -> verify -> export`), customer-managed execution, and evidence review.

On the proof layer, current `main` replay is 3/3 PASS for the published matrix (`replica_overprovisioning`, `cpu_pressure`, `memory_pressure`).

If you share target clusters/namespaces and constraints, we can use a 20-minute call to confirm fit, scope, and next step owners.

## 3) 20-minute call opener (short)

Thanks for joining. In 20 minutes, we should confirm three points:
1. Is your Kubernetes/GPU assessment scope a fit for ModeKeeper public core?
2. Can we proceed with strict read-only verify-first assessment in your environment?
3. Do we have clear owners and next steps for evidence review?

Boundary reminder: public core is frozen at `v0.1.33`; apply is separate/gated; current replayable proof tranche is 3/3 PASS for the published three-scenario matrix.

## 4) What we can say

Allowed first-contact claims:
- ModeKeeper public core is verify-first and strict read-only for Kubernetes/GPU cost and risk assessment.
- Public baseline behavior is frozen at `v0.1.33`.
- Public default workflow is `observe -> plan -> verify -> export`.
- Execution boundary is customer-managed in customer environments.
- Apply/implementation is separate licensed/gated path, not baseline public evaluation.
- Replayable proof evidence exists and currently passes 3/3 for the published matrix on current `main`.
- The 3/3 replay result supports verify-first proof rigor for that matrix only.

## 5) What we must not say

Disallowed first-contact claims:
- Universal/exhaustive detection or coverage across all Kubernetes/GPU workloads or environments.
- Guaranteed savings, guaranteed ROI, or guaranteed risk reduction.
- Vendor-operated or autonomous production execution.
- Public availability of apply/implementation capabilities.
- Any claim that replay 3/3 means broad or complete production coverage.
- Any claim that public product breadth expanded beyond frozen core.

## 6) Internal usage note

When phrasing is uncertain, use `docs/SNAPSHOT.md` wording verbatim or reduce claim strength.
