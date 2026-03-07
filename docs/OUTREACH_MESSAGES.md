# OUTREACH_MESSAGES

First-contact outreach templates, strictly aligned to `docs/OUTREACH_PACK.md` and `docs/SNAPSHOT.md` (with boundary consistency from `docs/BUYER_10MIN.md` and `docs/BUYER_PROOF_PACK.md`).

## 1) GPU/ML platform buyer

Initial message:

Hi {{Name}} - ModeKeeper is a verify-first, strict read-only assessment for Kubernetes/GPU cost and risk.

Public core is frozen at `v0.1.33`, and the current replayable proof tranche on `main` is 3/3 PASS for `replica_overprovisioning`, `cpu_pressure`, and `memory_pressure`.

Follow-up after positive reply:

Great. For first contact, we keep scope to read-only assessment (`observe -> plan -> verify -> export`) with customer-managed execution.

If useful, we can do a short fit check on your target clusters/namespaces and review the replay evidence boundary.

What this template is allowed to claim:
- Verify-first strict read-only Kubernetes/GPU assessment, frozen public core (`v0.1.33`), and replayable 3/3 PASS for the published matrix only.

## 2) Platform/SRE buyer

Initial message:

Hi {{Name}} - quick check if this is relevant: ModeKeeper stays in strict read-only assessment first (`observe -> plan -> verify -> export`) for Kubernetes/GPU cost and risk.

Public baseline is frozen at `v0.1.33`; apply/mutate is separate and gated.

Follow-up after positive reply:

Thanks. We can keep this to a short boundary review: customer-managed runtime, verify-first evidence flow, and current replayable proof status (3/3 PASS on the published matrix).

If fit is confirmed, we align owners for evidence review as the next step.

What this template is allowed to claim:
- Read-only verify-first workflow, customer-managed execution boundary, gated apply separation, and published 3/3 replay result without implying broader coverage.

## 3) Procurement/Security entry

Initial message:

Hi {{Name}} - for first contact, ModeKeeper’s public core is verify-first and strict read-only for Kubernetes/GPU cost and risk assessment.

Baseline is frozen at `v0.1.33`, with replayable proof on current `main` at 3/3 PASS for `replica_overprovisioning`, `cpu_pressure`, and `memory_pressure`.

Follow-up after positive reply:

Understood. We can keep the review to evidence and boundaries: read-only workflow, customer-managed execution, and separate gated apply path.

Then we align on the minimal artifact review path for your procurement/security process.

What this template is allowed to claim:
- Evidence-bound first-contact claims only: frozen public core, verify-first read-only workflow, customer-managed boundary, gated apply, and 3/3 replay for the published scenarios only.
