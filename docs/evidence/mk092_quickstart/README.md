# MK-092 Quickstart Evidence (file source)

Это **curated** evidence (коммитнутые выходы), чтобы показывать ModeKeeper без k8s.

Показывает:
- `telemetry.points[].ts_ms` всегда присутствует
- optional `node` / `gpu_model` в points (если есть в источнике)
- `environment.unstable=true`, если в окне наблюдения >1 node или >1 gpu_model

## Input (committed)
- observe_mixed_env.jsonl

## Outputs (committed, curated minimum)
- out_observe/observe_latest.json
- out_closed_loop/closed_loop_latest.json
- out_closed_loop/summary.md
- out_closed_loop/k8s_plan.json
- out_closed_loop/k8s_plan.kubectl.sh
- out_closed_loop/policy_bundle_latest.json
- out_watch/watch_latest.json
- out_watch/watch_summary.md
- out_watch/iter_000{1,2}/(closed_loop_latest.json, summary.md, k8s_plan.json, k8s_plan.kubectl.sh, policy_bundle_latest.json)

## Reproduce (recommended — DOES NOT dirty the repo)
1) mk observe
   mk observe --duration 1s --source file --path docs/evidence/mk092_quickstart/observe_mixed_env.jsonl --out /tmp/mk092/out_observe

2) mk closed-loop run (dry-run)
   mk closed-loop run --scenario drift --dry-run --observe-source file --observe-path docs/evidence/mk092_quickstart/observe_mixed_env.jsonl --out /tmp/mk092/out_closed_loop

3) mk closed-loop watch (2 iterations, dry-run)
   mk closed-loop watch --scenario drift --dry-run --observe-source file --observe-path docs/evidence/mk092_quickstart/observe_mixed_env.jsonl --out /tmp/mk092/out_watch --interval 1s --max-iterations 2
