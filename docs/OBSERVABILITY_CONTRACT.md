# Observability Contract v1

## Purpose

Define the canonical input and evidence contract for ModeKeeper's verify-first, read-only assessment path in customer-managed environments.

This contract standardizes what evidence is required to classify findings as `signal_found`, `no_actionable_signal`, or `insufficient_evidence`.

## Input Classes

### Mandatory Inputs

- Kubernetes object context (namespace/workload identity required for scoped assessment output).
- Deployment/pod spec context (to interpret runtime intent and scheduling constraints).
- Requests/limits context (to evaluate cost/risk patterns tied to resource declarations).
- Metrics window metadata (`window_s` and sample coverage signal for any metric-backed claim).

### Optional Inputs

- Rollout state history.
- Pod restarts and condition history.
- Logs.
- Events.
- GPU telemetry/allocation details (mandatory only when GPU-targeted patterns are in scope).

If optional inputs are absent, output classification must explicitly report `insufficient_evidence` where needed rather than infer unsupported conclusions.

## Supported Evidence Families

| evidence family | description | typical sources | required for |
|---|---|---|---|
| kube object context | workload identity and topology context | API object metadata | all pattern evaluation |
| deployment/pod spec | runtime intent, scheduling knobs, container config | Deployment/StatefulSet/Pod specs | most workload patterns |
| requests/limits | declared resource reservation boundaries | container resources in pod specs | CPU/memory/GPU sizing patterns |
| rollout state | rollout stability and transition context | rollout status/history | confidence gating for active changes |
| pod restarts/conditions | reliability and pressure indicators | pod status conditions, restart counters | risk/pressure patterns |
| logs | workload symptom evidence | container/app logs | corroborative context (optional) |
| metrics window | utilization/latency/throughput signal over time | metrics backends | metric-backed pattern classification |
| events | scheduler/runtime/system event context | Kubernetes events | failure/constraint corroboration |
| GPU telemetry/allocation | GPU reservation and activity context | DCGM/NVIDIA metrics, allocation metadata | GPU patterns |

## Evidence Quality Fields Proposal

Each pattern evaluation output should include:

- `coverage_ok`: boolean summary of whether evidence coverage is sufficient for the claim.
- `sample_count`: number of usable samples considered.
- `window_s`: effective observation window in seconds.
- `sources_seen`: list of evidence sources actually observed.
- `evidence_quality`: normalized quality label (for example: `high`, `medium`, `low`).
- `insufficient_evidence_reasons`: explicit reasons when evidence is incomplete or unreliable.

## Classification Rules (Public v1)

- Use `signal_found` when evidence quality and coverage support a concrete, review-worthy finding.
- Use `no_actionable_signal` when evidence is sufficient and no meaningful optimization/risk pattern is indicated.
- Use `insufficient_evidence` when quality/coverage is not adequate for a reliable claim.

Lack of evidence is a first-class result, not a silent failure.

## Boundary Notes

- Contract defines read-only assessment evidence and output semantics only.
- Collection and execution remain customer-managed.
- Apply/implementation is outside this public contract and remains a separate licensed/gated path.
