# Ideal Customer Profile (Public)

This ICP is intentionally narrow for the public, verify-first, read-only ModeKeeper path.

## Primary ICP (first target)

Mid-market to enterprise teams running Kubernetes workloads (including GPU where relevant) that need evidence-first cost/risk assessment before any change window.

Primary buyer group:
- Platform/SRE lead as technical owner
- FinOps or engineering finance partner
- Security/procurement reviewer in the evaluation chain

## Recommended first wedge

Start with one high-spend or high-risk namespace/workload group where the team already suspects overprovisioning or burst-related instability, and can run read-only assessment in a customer-managed environment.

Good first wedge shape:
- 1-2 clusters
- 5-15 priority workloads
- 2-4 week decision window

## Firmographic traits

- 150+ employee engineering organization (or equivalent operational complexity).
- Multi-team Kubernetes ownership with explicit review/approval processes.
- Meaningful monthly cloud/container spend where optimization outcomes are material.

## Technical/environment traits

- Kubernetes in production or production-like environments.
- Ability to run customer-managed CLI workflows and export artifacts.
- Read-only access path available (direct API read access or customer-run collection).
- Enough telemetry to support useful assessment windows (or willingness to test evidence sufficiency explicitly).

## Buying pain traits

- Cost pressure with low confidence in where safe savings exist.
- Repeated incidents tied to requests/limits/scaling posture.
- Change hesitation because prior tuning created regressions.
- Internal requirement for procurement/security/platform review artifacts before implementation work.

## Disqualifiers / low-fit cases

- Team expects autonomous vendor-operated apply as the initial motion.
- Team cannot provide a customer-managed read-only data path.
- No clear owner, no scoped workloads, and no measurable decision criteria.
- Very small environments where assessment overhead likely exceeds potential value.
- Requirement for universal detection guarantees across all workloads and telemetry conditions.
