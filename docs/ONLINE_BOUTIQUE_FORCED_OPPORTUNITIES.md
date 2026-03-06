# Online Boutique Forced Opportunities (Read-Only Validation)

Purpose: provide customer-managed, reproducible scenario assets that force non-zero ModeKeeper read-only assessment output for Online Boutique.

Boundary:
- This runbook is public/read-only assessment only.
- ModeKeeper apply/implementation is not used here.
- Any cluster mutation below is explicit, customer-managed `kubectl` execution for scenario setup/cleanup.

Assets location:
- `examples/online-boutique/forced-opportunity/manifests/`
- `examples/online-boutique/forced-opportunity/scripts/`

## Prerequisites

- Running Online Boutique deployment in your cluster.
- `kubectl` context set to the target cluster.
- `mk` CLI available locally.

## Scenario 1: Oversized Requests

Objective: force oversized CPU/memory request signal on `frontend` (first intended non-zero proof path).

Apply scenario setup:

```bash
examples/online-boutique/forced-opportunity/scripts/apply_scenario.sh apply oversized_requests onlineboutique
```

Run assessment:

```bash
examples/online-boutique/forced-opportunity/scripts/run_readonly_assessment.sh onlineboutique frontend report/online_boutique/forced_oversized 60s
```

Helper output layout:
- `report/online_boutique/forced_oversized/observe` from `mk observe --source k8s-logs`
- `report/online_boutique/forced_oversized/closed_loop` from `mk closed-loop run --observe-source k8s-logs`
- `report/online_boutique/forced_oversized/watch` from `mk closed-loop watch --observe-source k8s-logs`

Expected assessment outcome: `assessment_result_class=signal_found` when evidence is sufficient.

Cleanup:

```bash
examples/online-boutique/forced-opportunity/scripts/apply_scenario.sh delete oversized_requests onlineboutique
```

This scenario uses `kubectl patch` and restores the pre-patch `frontend` resources from local state. If local state is missing, restore your baseline `frontend` deployment config manually.

## Scenario 2: Replica Overprovisioning

Objective: force low-utilization overprovisioning signal.

Apply scenario setup:

```bash
examples/online-boutique/forced-opportunity/scripts/apply_scenario.sh apply replica_overprovisioning onlineboutique
```

Run assessment:

```bash
examples/online-boutique/forced-opportunity/scripts/run_readonly_assessment.sh onlineboutique emailservice report/online_boutique/forced_replicas 60s
```

Expected assessment outcome: `assessment_result_class=signal_found` when evidence is sufficient.

Cleanup:

```bash
examples/online-boutique/forced-opportunity/scripts/apply_scenario.sh delete replica_overprovisioning onlineboutique
```

This scenario uses `kubectl patch` and restores the pre-patch `emailservice` replica count from local state. If local state is missing, restore your baseline replica count manually.

## Scenario 3: Burst Traffic

Objective: force burst sensitivity / scaling-gap conditions.

Apply scenario setup:

```bash
examples/online-boutique/forced-opportunity/scripts/apply_scenario.sh apply burst_traffic onlineboutique
kubectl -n onlineboutique wait --for=condition=Complete --timeout=10m job/modekeeper-burst-traffic
```

Run assessment:

```bash
examples/online-boutique/forced-opportunity/scripts/run_readonly_assessment.sh onlineboutique checkoutservice report/online_boutique/forced_burst 60s
```

Expected assessment outcome: `assessment_result_class=signal_found` when evidence is sufficient.

Cleanup:

```bash
examples/online-boutique/forced-opportunity/scripts/apply_scenario.sh delete burst_traffic onlineboutique
```

## Notes

- If telemetry coverage is weak (for example short window, sparse samples, missing required source), `assessment_result_class=insufficient_evidence` is the correct result.
- Use generated summaries and handoff artifacts for enterprise review (`mk export handoff-pack`).
