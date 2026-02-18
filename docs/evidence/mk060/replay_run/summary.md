started_at: 2026-02-11T14:57:57+00:00
finished_at: 2026-02-11T14:57:57+00:00
duration_s: 0
mode: CLOSED_LOOP
apply_requested: False
dry_run: True
kill_switch_active: False
paid_enabled: False
verify_ok: None
apply_decision_summary: apply not requested (dry-run)
apply_blocked_reason: None
k8s_plan_path: docs/evidence/mk060/replay_run/k8s_plan.json
k8s_plan_items: 4
k8s_kubectl_plan_path: docs/evidence/mk060/replay_run/k8s_plan.kubectl.sh
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
