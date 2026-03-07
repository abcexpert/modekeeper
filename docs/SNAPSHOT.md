# ModeKeeper Public Snapshot

This document is a public-facing positioning and status snapshot for ModeKeeper.
It is intentionally limited to buyer-safe, enterprise-review-safe context.

## Product position (public)

ModeKeeper is a verify-first, read-only assessment product for Kubernetes/GPU cost and risk, with customer-managed execution and a change-ready handoff pack for enterprise review.
The default public workflow stays in strict read-only assessment before any mutation decision.

Core positioning pillars:
- verify-first
- read-only assessment
- Kubernetes/GPU cost and risk visibility before change
- change-ready handoff pack for controlled continuation
- enterprise review as a first-class step
- customer-managed execution (no vendor-operated runtime implication)

## Current public state

- Public distribution is available via GitHub and PyPI (`modekeeper`).
- Public docs are aligned around safe evaluation and evidence-first decisioning.
- Public offer and ICP docs are available for buyer qualification and scope fit.
- Canonical public workflow remains strict read-only assessment: `observe -> plan -> verify -> export`.
- Apply/mutate is a separate licensed and gated path and is not baseline public evaluation.
- Runtime execution boundary remains customer-managed in customer environments.
- Public core behavior is frozen at `v0.1.33` baseline.
- Post-baseline updates on current `main` are limited to bugfixes, contract-drift correction, proof-layer necessity, and boundary-safe wording alignment.
- Post-`v0.1.33` replayable proof tranche is complete on current `main` via `scripts/proof-matrix-replay.sh`:
  `replica_overprovisioning`, `cpu_pressure`, and `memory_pressure` pass (3/3).

## What the replayable proof tranche proves

- The proof harness is replayable and deterministic for the published matrix scenarios (3/3 pass on current `main`).
- Public verify-first claims are supported by reproducible evidence replay, not one-off run output.
- This tranche increases confidence in proof-layer rigor only; it does not widen public product surface.

## Claims boundary (current)

Justified now:
- ModeKeeper public core is a verify-first, strict read-only assessment workflow for Kubernetes/GPU cost and risk.
- Public baseline behavior is frozen at `v0.1.33`, with post-baseline changes constrained as listed above.
- Replayable proof evidence exists for the current published three-scenario matrix and passes end-to-end.
- Customer-managed runtime boundary and gated apply separation are explicit and preserved.

Explicitly not claimed:
- Universal or exhaustive detection/coverage across all Kubernetes/GPU workloads, incidents, or environments.
- Guaranteed savings or guaranteed risk reduction outcomes.
- Autonomous or vendor-operated production execution.
- Public availability of apply/implementation capabilities.
- Expansion of public product breadth beyond the frozen core baseline.

## Canonical public workflow (high-level)

1. Observe workload/runtime signals without changing cluster state.
2. Build a proposed plan in dry-run mode.
3. Verify plan readiness in read-only mode.
4. Export a handoff pack for enterprise/security/platform review.

This sequence is designed to support Kubernetes/GPU change planning with explicit risk and cost review before any apply decision.

## Enterprise review and handoff

Public evaluation outputs are packaged as a change-ready handoff pack so customer teams can:
- validate integrity,
- review evidence and plan context,
- continue assessment or change planning under internal controls.

Handoff artifacts are intended for procurement, security, and platform stakeholders and support customer-managed continuation without vendor runtime access.

## Execution boundary

ModeKeeper public workflows do not imply vendor-operated execution.
Customers:
- run in their own Kubernetes/runtime environments,
- control permissions and data boundaries,
- decide whether to stop at read-only assessment or enter licensed apply under their own governance.

## Canonical references

- `docs/WORKFLOW.md` - public execution model and boundary semantics.
- `docs/HANDOFF.md` - handoff pack contents and verification policy.
- `docs/OFFER.md` - public offer boundary and buyer-safe scope.
- `docs/ICP.md` - primary fit profile and disqualifiers.
- `docs/RELEASE.md` - public release boundary (GitHub/PyPI).
- `docs/STATUS.md` - current public progress summary.
- `README.md` - public product entrypoint.
