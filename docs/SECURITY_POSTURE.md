# Security Posture

This page is a public showroom map for Security and Procurement review. It is intentionally link-first and points to canonical policy/workflow docs.
For concise RFI-style Q&A, see `docs/SECURITY_QA.md`.
Compliance control mapping: `docs/COMPLIANCE_MATRIX.md`.
Threat model for enterprise review: `docs/THREAT_MODEL.md`.

## Execution model

- Public runtime is read-only by default: plan/verify/export flows are intended to be non-mutating.
- Public evidence artifacts are generated for review and traceability.
- Mutation/apply paths are hard-gated and blocked unless required controls pass.

Canonical references:
- `README.md`
- `docs/WORKFLOW.md`
- `docs/QUICKSTART.md`

## Safety gates for mutation

Mutation/apply requires all gates:
- `verify_ok=true`
- absolute kill-switch (`MODEKEEPER_KILL_SWITCH=1` blocks apply/mutate)
- valid license + required entitlement

Canonical references:
- `docs/WORKFLOW.md`
- `docs/PLAYBOOKS.md`

## Audit and evidence

Primary evidence is produced as run artifacts (for example plan/verify/export/decision-trace outputs) and can be reviewed as a pack.

Canonical references:
- `docs/BUYER_PROOF_PACK.md`
- `docs/WORKFLOW.md`

## Supply-chain guardrails

Public distribution guardrails include:
- wheel-only public release flow
- denylist-based wheel audit and hard bans
- explicit release rules and smoke-gated tagging

Canonical references:
- `docs/RELEASE.md`
- `docs/DISTRIBUTION_POLICY.md`

## Data handling

- Secrets, keys, licenses, and credentials must never be committed.
- Token/key/license material is local/runtime managed per policy and workflow docs.
- License path resolution and verification behavior are documented in workflow references.

Canonical references:
- `docs/DISTRIBUTION_POLICY.md`
- `docs/WORKFLOW.md`
