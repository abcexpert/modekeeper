started_at: 2026-02-11T15:27:47+00:00
finished_at: 2026-02-11T15:27:47+00:00
duration_s: 0
mode: CLOSED_LOOP
apply_requested: False
dry_run: True
kill_switch_active: False
paid_enabled: False
verify_ok: None
apply_decision_summary: apply not requested (dry-run)
apply_blocked_reason: None
opportunity_hours_est: 0.00025
opportunity_tokens_est: 0.0
opportunity_usd_est: 0.0
opportunity_assumptions: {"active_signals":["drift","burst"],"baseline_window_s":9.0,"formulas":{"opportunity_hours_est":"baseline_window_s/3600 * opportunity_fraction","opportunity_tokens_est":"throughput_avg_per_s * baseline_window_s * opportunity_fraction","opportunity_usd_est":"opportunity_hours_est * gpu_hour_usd * gpu_count"},"gpu_count":0,"gpu_hour_usd":0.0,"model":"heuristic_v1","notes":"throughput_avg_per_s=0 when source lacks throughput","opportunity_fraction":0.1,"throughput_avg_per_s":0.0,"throughput_unit":"tokens_per_sec (assumed)"}
k8s_plan_path: docs/evidence/mk061/replay_run/k8s_plan.json
k8s_plan_items: 4
k8s_kubectl_plan_path: docs/evidence/mk061/replay_run/k8s_plan.kubectl.sh
k8s_namespace: default
k8s_deployment: trainer
k8s_verify_report_path: None
k8s_apply_report_path: None
proposed:
- grad_accum_steps -> 8
- microbatch_size -> 32
- dataloader_prefetch_factor -> 2
- concurrency -> 4
applied:
- grad_accum_steps -> 8 | applied=False blocked=False reason=dry_run
- microbatch_size -> 32 | applied=False blocked=False reason=dry_run
- dataloader_prefetch_factor -> 2 | applied=False blocked=False reason=dry_run
- concurrency -> 4 | applied=False blocked=False reason=dry_run
