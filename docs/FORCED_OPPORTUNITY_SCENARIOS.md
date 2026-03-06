# Forced Opportunity Scenarios v1

## Purpose

Define controlled, docs-only proof scenarios that should produce non-zero assessment signal and proposal output under ModeKeeper's verify-first, read-only path.

These scenarios are for assessment validation and public specification. They do not implement mutation/apply behavior.

## Scope

- Canonical external workload: [Online Boutique](https://github.com/GoogleCloudPlatform/microservices-demo)
- Customer-managed execution context.
- Public assessment outputs only (`observe -> plan -> verify -> export`).

## Scenario 1: Oversized Requests

- Objective: confirm detection of materially oversized CPU/memory requests versus observed usage.
- Setup idea: raise requests for a stable service while keeping baseline traffic modest.
- Target workload/service: `productcatalogservice` (or similar steady-state service).
- Expected signal(s): low utilization relative to declared requests; cost inefficiency indication.
- Expected output class: `signal_found`.
- Non-zero proposal expected: yes.
- Non-zero ROI expected: yes.
- Rollback/cleanup notes: restore original requests/limits and confirm rollout stabilization.

## Scenario 2: Replica Overprovisioning

- Objective: confirm signal when replicas are materially above sustained demand.
- Setup idea: increase replicas for a low-traffic service without corresponding load increase.
- Target workload/service: `emailservice` or `currencyservice`.
- Expected signal(s): low per-replica utilization and excess capacity indication.
- Expected output class: `signal_found`.
- Non-zero proposal expected: yes.
- Non-zero ROI expected: yes.
- Rollback/cleanup notes: return replica count to baseline and verify pod count convergence.

## Scenario 3: CPU Pressure

- Objective: confirm pressure/risk classification under CPU saturation or throttling.
- Setup idea: generate sustained CPU-heavy traffic against one service tier.
- Target workload/service: `checkoutservice`.
- Expected signal(s): throttle/saturation indicators; potential latency/reliability risk.
- Expected output class: `signal_found`.
- Non-zero proposal expected: yes.
- Non-zero ROI expected: optional (risk reduction may dominate direct cost).
- Rollback/cleanup notes: stop pressure workload and validate recovery of throttling/latency signals.

## Scenario 4: Memory Pressure

- Objective: confirm risk signal for memory pressure, restart, or near-OOM behavior.
- Setup idea: induce memory-stressing request patterns or constrained limits on a candidate service.
- Target workload/service: `recommendationservice`.
- Expected signal(s): memory pressure indicators, restart/condition evidence.
- Expected output class: `signal_found`.
- Non-zero proposal expected: yes.
- Non-zero ROI expected: optional (stability improvement may be primary outcome).
- Rollback/cleanup notes: restore limits/config and verify restart/condition normalization.

## Scenario 5: Burst Traffic

- Objective: confirm burst-sensitivity and scaling-gap signal under transient demand spikes.
- Setup idea: apply short high-rate traffic bursts separated by cooldown intervals.
- Target workload/service: frontend + `checkoutservice` path.
- Expected signal(s): latency and/or queue pressure during bursts; delayed scaling response.
- Expected output class: `signal_found`.
- Non-zero proposal expected: yes.
- Non-zero ROI expected: yes.
- Rollback/cleanup notes: stop burst generator and confirm service/replica behavior returns to baseline.

## Scenario 6: GPU Idle Reservation

- Objective: confirm detection of reserved GPU capacity with low sustained utilization.
- Setup idea: schedule a GPU-requesting workload with low duty cycle or idle intervals.
- Target workload/service: GPU-enabled inference worker in Online Boutique-compatible extension path.
- Expected signal(s): reserved GPU with low activity over observation window.
- Expected output class: `signal_found` (or `insufficient_evidence` if GPU telemetry is unavailable).
- Non-zero proposal expected: yes when telemetry is sufficient.
- Non-zero ROI expected: yes when telemetry is sufficient.
- Rollback/cleanup notes: remove GPU reservation test configuration and validate normal allocation state.

## Notes

- Scenarios intentionally force opportunity conditions to validate assessment surface quality.
- If expected telemetry is missing, explicit `insufficient_evidence` classification is the correct result.
- Implementation playbooks and automation are out of scope for this pass.
