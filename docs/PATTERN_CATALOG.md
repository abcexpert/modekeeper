# Pattern Catalog v1

## Purpose

Define ModeKeeper's public, verify-first catalog of observable Kubernetes/GPU cost and risk patterns for read-only assessment in customer-managed environments.

This catalog defines broad detectable pattern classes and expected evidence handling. It does not claim exhaustive coverage.

## Outcome Classes

- `signal_found`: evidence supports an actionable or review-worthy pattern.
- `no_actionable_signal`: evidence is sufficient, but no meaningful optimization/risk signal is currently indicated.
- `insufficient_evidence`: available evidence is not strong enough to support a reliable claim.

## 1) CPU / Memory Patterns

| pattern_name | what it means | required inputs | minimum window | expected evidence | insufficient_evidence conditions | expected output class | proposal expectation |
|---|---|---|---|---|---|---|---|
| cpu_request_oversized_vs_usage | CPU requests are materially above observed sustained use, indicating potential over-reservation cost. | requests/limits, metrics window (CPU usage), pod/workload mapping | 30m | sustained low CPU utilization relative to request across multiple samples | missing CPU usage metrics, sparse samples, unknown request values | `signal_found` or `no_actionable_signal` | actionable proposal expected when `signal_found` |
| cpu_throttle_pressure | CPU throttling suggests CPU pressure and performance risk. | pod/container CPU throttling metrics, requests/limits, rollout state | 15m | repeated throttle periods with correlated workload pressure | throttling metric missing, insufficient sample_count, unstable rollout | `signal_found` or `insufficient_evidence` | actionable proposal expected when `signal_found` |
| memory_request_oversized_vs_working_set | Memory requests are materially above observed working set, indicating possible over-allocation. | requests/limits, memory working set metrics, pod/workload mapping | 30m | working set materially below request over stable period | missing memory metrics, request missing, too-short window | `signal_found` or `no_actionable_signal` | actionable proposal expected when `signal_found` |
| memory_pressure_oom_risk | Memory pressure/evictions/restarts indicate reliability risk and possible under-sizing. | pod restarts/conditions, events, memory usage metrics, rollout state | 15m | OOM/restart or pressure signals plus memory saturation context | no restart/condition/event data, no memory telemetry, rollout instability | `signal_found` or `insufficient_evidence` | actionable proposal expected when `signal_found` |

## 2) Replica / Scheduling Patterns

| pattern_name | what it means | required inputs | minimum window | expected evidence | insufficient_evidence conditions | expected output class | proposal expectation |
|---|---|---|---|---|---|---|---|
| replica_overprovisioning_low_util | Replica count appears high relative to sustained demand/utilization. | workload replicas, usage metrics, service traffic context | 30m | low per-replica utilization and low request pressure across window | missing utilization/traffic evidence, short window, active scaling rollout | `signal_found` or `no_actionable_signal` | actionable proposal expected when `signal_found` |
| pending_unschedulable_capacity_risk | Pods remain pending/unschedulable due to capacity/constraints, indicating availability risk. | pod conditions, events, scheduler-related status, node context | 10m | repeated scheduling failures with consistent reason codes | events unavailable, condition history missing, single transient sample | `signal_found` or `insufficient_evidence` | actionable proposal expected when `signal_found` |
| topology_fragmentation_idle_capacity | Requested footprint and placement constraints fragment capacity, driving cost inefficiency. | pod spec (affinity/anti-affinity), node labels/capacity, scheduling outcomes | 30m | uneven placement and stranded allocatable resources | missing node/scheduler context, incomplete pod spec, insufficient sample_count | `signal_found` or `insufficient_evidence` | proposal optional |

## 3) GPU Patterns

| pattern_name | what it means | required inputs | minimum window | expected evidence | insufficient_evidence conditions | expected output class | proposal expectation |
|---|---|---|---|---|---|---|---|
| gpu_idle_reservation | GPU resources are reserved but show consistently low activity, indicating avoidable cost. | GPU allocation context, GPU telemetry/utilization, workload mapping | 30m | low GPU utilization while reservation remains active | no GPU telemetry, allocation unknown, insufficient sample_count | `signal_found` or `insufficient_evidence` | actionable proposal expected when `signal_found` |
| gpu_mismatch_request_profile | GPU type/count appears mismatched to observed demand profile. | GPU request/allocation, telemetry, pod spec | 30m | sustained utilization pattern inconsistent with provisioned GPU profile | missing allocation metadata, telemetry gaps, frequent rollout churn | `signal_found` or `insufficient_evidence` | proposal optional |
| gpu_contention_or_saturation | GPU near-saturation or contention indicates performance/risk pressure. | GPU utilization/saturation telemetry, pod state, service latency context | 15m | sustained high utilization with correlated latency or backlog signs | no GPU metrics, no service/queue context, sample window too short | `signal_found` or `insufficient_evidence` | actionable proposal expected when `signal_found` |

## 4) Service / Queue / Latency Patterns

| pattern_name | what it means | required inputs | minimum window | expected evidence | insufficient_evidence conditions | expected output class | proposal expectation |
|---|---|---|---|---|---|---|---|
| service_latency_with_low_util | Latency issues occur despite low resource utilization, indicating non-capacity bottleneck risk. | service latency metrics, workload utilization, logs/events context | 15m | elevated latency while CPU/memory/GPU are not saturated | missing latency metrics, no correlated utilization data, low sample_count | `signal_found` or `insufficient_evidence` | proposal optional |
| queue_backlog_growth | Queue depth or processing lag grows over window, indicating throughput gap and risk. | queue depth/lag metrics, worker replica state, rollout context | 15m | upward backlog trend with stable or constrained workers | queue metric missing, no worker/replica context, short window | `signal_found` or `insufficient_evidence` | actionable proposal expected when `signal_found` |
| burst_sensitivity_scaling_gap | Traffic bursts create transient pressure not matched by replica/scheduling behavior. | request rate metrics, replica timeline, pod scheduling/events | 15m | burst periods with pressure/restarts/latency before recovery | missing traffic-rate signal, no replica timeline, event history absent | `signal_found` or `insufficient_evidence` | actionable proposal expected when `signal_found` |

## Notes

- Pattern outputs remain advisory within a read-only assessment.
- Execution and evidence collection remain customer-managed.
- Apply/implementation decisions remain outside this public assessment path.
