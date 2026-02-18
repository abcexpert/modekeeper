started_at: 2026-02-14T07:19:36+00:00
finished_at: 2026-02-14T07:19:36+00:00
duration_s: 0
mode: CLOSED_LOOP
policy: chord
apply_requested: False
dry_run: True
kill_switch_active: False
paid_enabled: False
verify_ok: None
apply_decision_summary: apply not requested (dry-run)
apply_blocked_reason: None
opportunity_hours_est: 4.2e-05
opportunity_tokens_est: 0.0
opportunity_usd_est: 0.0
opportunity_assumptions: {"active_signals":["gpu_saturated"],"baseline_window_s":3.0,"formulas":{"opportunity_hours_est":"baseline_window_s/3600 * opportunity_fraction","opportunity_tokens_est":"throughput_avg_per_s * baseline_window_s * opportunity_fraction","opportunity_usd_est":"opportunity_hours_est * gpu_hour_usd * gpu_count"},"gpu_count":0,"gpu_hour_usd":0.0,"model":"heuristic_v1","notes":"throughput_avg_per_s=0 when source lacks throughput","opportunity_fraction":0.05,"throughput_avg_per_s":0.0,"throughput_unit":"tokens_per_sec (assumed)"}
k8s_plan_path: docs/evidence/mk092_quickstart/out_watch/iter_0002/k8s_plan.json
k8s_plan_items: 1
k8s_kubectl_plan_path: docs/evidence/mk092_quickstart/out_watch/iter_0002/k8s_plan.kubectl.sh
k8s_namespace: default
k8s_deployment: trainer
k8s_verify_report_path: None
k8s_apply_report_path: None
proposed:
- microbatch_size -> 16
applied:
- microbatch_size -> 16 | applied=False blocked=False reason=dry_run
