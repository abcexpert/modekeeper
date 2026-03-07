# WORKFLOW (Public)

Primary onboarding path: `docs/QUICKSTART.md`.
This document defines the public-facing execution workflow and boundary model.
ModeKeeper public workflow is verify-first, strict read-only assessment for Kubernetes/GPU cost and risk.

## Workflow principles

- Verify-first: assessment starts from evidence and safety checks before any mutation.
- Strict read-only public path: canonical public flow is `observe -> plan -> verify -> export`.
- Customer-managed runtime: execution happens in customer-controlled Kubernetes environments.
- Export boundary: outputs are packaged as a change-ready handoff pack for enterprise review.
- Licensed apply is gated: mutate/apply is a separate, controlled path and not baseline public assessment.

## Canonical public flow (read-only assessment)

### 1) Observe
Collect environment and workload signals without changing cluster state.

Example:

```bash
./.venv/bin/mk observe --source k8s --k8s-namespace default --k8s-deployment trainer --container trainer --duration 2m --out ./out/observe
```

### 2) Plan
Generate a proposed change plan in dry-run mode.

Example:

```bash
./.venv/bin/mk closed-loop run --scenario drift --dry-run --out ./out/closed_loop
```

Typical artifacts:
- `closed_loop_latest.json`
- `k8s_plan.json`
- `k8s_plan.kubectl.sh` (rendered script, not executed by this step)
- `summary.md`
- `policy_bundle_latest.json`

### 3) Verify (no mutation)
Validate the plan against current cluster state before any apply decision.

Example:

```bash
./.venv/bin/mk k8s verify --plan ./out/closed_loop/k8s_plan.json --out ./out/closed_loop
```

Output includes `k8s_verify_latest.json` with verification status used for enterprise review and gating.

### 4) Export review and handoff artifacts
Package read-only results for buyer/security/platform review and controlled continuation.

Example:

```bash
./.venv/bin/mk export handoff-pack --in ./out/closed_loop --out ./out/handoff
```

Expected handoff pack includes integrity metadata and verification helpers (manifest/checksums/summary).

## Licensed apply path (high-level gate)

Licensed apply exists as a separate gated path and is not part of default public assessment.

Boundary semantics:
- apply/mutate is allowed only when licensing and safety gates are satisfied,
- verify result must indicate readiness before apply is permitted,
- kill-switch and safety controls can block mutation,
- execution remains customer-managed in customer runtime.

For public-facing evaluation, stay in the read-only path unless the customer explicitly enters licensed apply under their own controls.

## Customer-managed execution model

ModeKeeper does not imply vendor-operated runtime.
Customers:
- run workflows in their own clusters,
- own permissions and data boundaries,
- decide when to stop at assessment or proceed to licensed apply.

This separation supports Kubernetes/GPU risk review before any change execution.

## Enterprise review boundary

Public workflow is designed for enterprise evaluation:
- deterministic artifacts for security/procurement/platform review,
- clear separation between assessment outputs and mutation actions,
- portable handoff pack for audit and internal decision workflows.

## See also

- `docs/QUICKSTART.md`
- `docs/HANDOFF.md`
- `docs/ENTERPRISE_EVALUATION.md`
- `docs/APPLY_SPEC.md`
- `docs/DISTRIBUTION_POLICY.md`
