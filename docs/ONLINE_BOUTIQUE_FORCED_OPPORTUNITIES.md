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

Objective: force oversized CPU/memory request signal.

Apply scenario setup:

```bash
examples/online-boutique/forced-opportunity/scripts/apply_scenario.sh apply oversized_requests default
```

Run assessment:

```bash
examples/online-boutique/forced-opportunity/scripts/run_readonly_assessment.sh default productcatalogservice report/online_boutique/forced_oversized 60s
```

Expected assessment outcome: `assessment_result_class=signal_found` when evidence is sufficient.

Cleanup:

```bash
examples/online-boutique/forced-opportunity/scripts/apply_scenario.sh delete oversized_requests default
```

Then restore your baseline deployment manifest for `productcatalogservice`.

## Scenario 2: Replica Overprovisioning

Objective: force low-utilization overprovisioning signal.

Apply scenario setup:

```bash
examples/online-boutique/forced-opportunity/scripts/apply_scenario.sh apply replica_overprovisioning default
```

Run assessment:

```bash
examples/online-boutique/forced-opportunity/scripts/run_readonly_assessment.sh default emailservice report/online_boutique/forced_replicas 60s
```

Expected assessment outcome: `assessment_result_class=signal_found` when evidence is sufficient.

Cleanup:

```bash
examples/online-boutique/forced-opportunity/scripts/apply_scenario.sh delete replica_overprovisioning default
```

Then restore your baseline replica count for `emailservice`.

## Scenario 3: Burst Traffic

Objective: force burst sensitivity / scaling-gap conditions.

Apply scenario setup:

```bash
examples/online-boutique/forced-opportunity/scripts/apply_scenario.sh apply burst_traffic default
kubectl -n default wait --for=condition=Complete --timeout=10m job/modekeeper-burst-traffic
```

Run assessment:

```bash
examples/online-boutique/forced-opportunity/scripts/run_readonly_assessment.sh default checkoutservice report/online_boutique/forced_burst 60s
```

Expected assessment outcome: `assessment_result_class=signal_found` when evidence is sufficient.

Cleanup:

```bash
examples/online-boutique/forced-opportunity/scripts/apply_scenario.sh delete burst_traffic default
```

## Notes

- If telemetry coverage is weak (for example short window, sparse samples, missing required source), `assessment_result_class=insufficient_evidence` is the correct result.
- Use generated summaries and handoff artifacts for enterprise review (`mk export handoff-pack`).
