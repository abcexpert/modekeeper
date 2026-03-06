# ModeKeeper Public Roadmap

## Product direction (public)
ModeKeeper is a verify-first operations product for SRE/MLOps/FinOps teams.
The public path is read-only by default (`observe -> dry-run plan -> verify -> ROI -> export`) so teams can assess safety, controls, and value before discussing execution changes.

Execution remains customer-managed: organizations run ModeKeeper in their own environment, with their own controls, identities, and change-management policy.

## What is available now
- Verify-first read-only assessment flow with reproducible evidence artifacts.
- Deterministic export bundles for reviewer handoff and audit sharing.
- Buyer/procurement packaging for security, risk, and architecture review.
- Enterprise evaluation index for structured multi-stakeholder review.
- Public documentation set focused on evaluation, safety posture, and procurement readiness.

Primary references: `README.md`, `docs/QUICKSTART.md`, `docs/PROCUREMENT_PACK.md`, `docs/ENTERPRISE_EVALUATION.md`, `docs/SECURITY_QA.md`.

## Roadmap themes

### 1) Stronger verify-first assessment
- Expand read-only assessment coverage for more real-world Kubernetes and platform scenarios.
- Improve evidence clarity so reviewers can quickly understand decisions, blockers, and expected impact.
- Keep outputs deterministic and easy to compare across runs and environments.

### 2) Customer-managed execution readiness
- Maintain a strict separation between read-only assessment and execution paths.
- Improve policy-friendly handoff artifacts that let customer operators review, approve, and execute changes in their own systems.
- Strengthen controls visibility needed for enterprise change governance.

### 3) Change-ready handoff packs
- Evolve export bundles into decision-ready handoff packs for platform, security, and CAB-style review.
- Improve artifact structure for traceability from observed state to proposed change intent.
- Reduce reviewer friction with clearer summaries and consistent evidence indexing.

### 4) Enterprise and procurement-safe posture
- Expand procurement-facing evidence for security and compliance workflows.
- Improve packaging for legal, risk, and architecture review cycles.
- Keep public artifacts and docs aligned with buyer due-diligence expectations.

### 5) Public showroom evolution (high level)
- Continue improving the public showroom as a safe, read-only evaluation experience.
- Add higher-level examples and proof narratives for common enterprise scenarios.
- Preserve a clear boundary: public roadmap communicates product direction, not internal delivery choreography.

## Evaluation path for new teams
1. Run the read-only quickstart flow and generate evidence artifacts.
2. Review verify and ROI outputs with platform/security stakeholders.
3. Export a handoff bundle for enterprise/procurement review.
4. Decide internally whether and how to progress toward customer-managed execution.

Start points: `docs/QUICKSTART.md`, `docs/BUYER_PROOF_PACK.md`, `docs/PROCUREMENT_PACK.md`.
