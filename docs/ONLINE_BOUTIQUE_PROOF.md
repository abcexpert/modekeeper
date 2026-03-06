# Online Boutique External Proof (Read-Only, Non-Zero Signal Path)

## Purpose

This page summarizes a confirmed public-docs proof pass showing a non-zero observable signal/proposal path on a realistic external workload (Online Boutique), while staying in verify-first, read-only assessment.

## Environment And Boundary

- Workload namespace: `onlineboutique`
- First proof target deployment: `frontend`
- Scenarios covered:
  - oversized requests
  - burst traffic
- Execution boundary:
  - customer-managed execution in customer environment
  - read-only assessment path for ModeKeeper (`observe`, `closed-loop run --dry-run`, `closed-loop watch --dry-run`)
  - no autonomous apply/implementation implied

## Exact Read-Only Path Used

```bash
mk observe --source k8s-logs
mk closed-loop run --dry-run --observe-source k8s-logs
mk closed-loop watch --dry-run --observe-source k8s-logs
```

## Confirmed Results

| Scenario | Flow | assessment_result_class | coverage_ok | sample_count | window_s | signal_count | actionable_proposal_count |
|---|---|---|---:|---:|---:|---:|---:|
| `forced_oversized` | `closed_loop` | `signal_found` | `True` | 18 | 6.687 | 1 | 2 |
| `forced_oversized` | `watch` | `signal_found` | `True` | 23 | 9.545 | 1 | 2 |
| `forced_burst` | `closed_loop` | `signal_found` | `True` | 174 | 58.842 | 1 | 2 |
| `forced_burst` | `watch` | `signal_found` | `True` | 179 | 60.012 | 1 | 2 |

Cleanup back to baseline was confirmed after the proof scenarios.

## Scope Statement

This is proof of a non-zero observable signal/proposal path under two forced scenarios with sufficient evidence quality. It is not a claim of universal detection across all workloads, clusters, or telemetry conditions.

## Local Artifact Boundary

Proof artifacts remain local/customer-managed and are not committed to git.

Canonical local artifact paths:
- `report/online_boutique/BUYER_PROOF_INDEX.md`
- `report/online_boutique/forced_oversized/**`
- `report/online_boutique/forced_burst/**`

