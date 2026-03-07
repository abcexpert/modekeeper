# ModeKeeper Public Offer (Read-Only Assessment)

## What ModeKeeper is

ModeKeeper is a verify-first, read-only assessment for Kubernetes/GPU cost and risk.
It is designed for customer-managed execution in customer environments, with a change-ready handoff pack for enterprise review.

Canonical public path:

`observe -> plan -> verify -> export`

## Who it is for

- Platform engineering teams running Kubernetes workloads with cost and reliability pressure.
- SRE teams that need evidence-first change planning before touching production settings.
- FinOps stakeholders who need transparent, reviewable cost/risk opportunities.
- Security/procurement reviewers who require auditable, non-mutating evaluation artifacts.

## What buyers get in the public path

- Strict read-only assessment workflow and documentation.
- Detection/evidence classification semantics for sufficient vs insufficient evidence.
- Customer-managed runbooks and reproducible commands for evaluation.
- Change-ready handoff artifacts for internal platform/security/procurement review.
- Public proof summary from an external realistic workload path (Online Boutique forced scenarios) showing non-zero signal/proposal outcomes in read-only mode.

## What is explicitly not included in the public path

- No autonomous apply or vendor-operated mutation workflow.
- No promise of universal detection across all workloads, clusters, or telemetry conditions.
- No guaranteed production outcome across every environment.
- No bundled private/proprietary implementation deliverables in this repository.

## Why verify-first matters

- Reduces operational risk by proving signal quality before any change decision.
- Improves enterprise review speed with evidence artifacts instead of opinion-only proposals.
- Preserves customer control over permissions, runtime boundaries, and change governance.

## Credibility from Online Boutique proof

The public proof summary documents two forced scenarios (`forced_oversized`, `forced_burst`) on Online Boutique with non-zero read-only signal/proposal outcomes under sufficient evidence.

This supports credibility for the public assessment path while remaining explicit about scope limits:
- It demonstrates a real external workload proof path.
- It does not claim universal production coverage.

References:
- [Online Boutique external proof summary](ONLINE_BOUTIQUE_PROOF.md)
- [Online Boutique forced-opportunity runbook](ONLINE_BOUTIQUE_FORCED_OPPORTUNITIES.md)

## Public assessment vs licensed/gated PRO apply

Public scope:
- verify-first read-only assessment (`observe -> plan -> verify -> export`)
- customer-managed execution and enterprise-review handoff artifacts

Separate licensed/gated PRO scope:
- apply/implementation workflow under explicit customer approval and governance
- outside the baseline public evaluation path

Reference:
- [Apply spec](APPLY_SPEC.md)
