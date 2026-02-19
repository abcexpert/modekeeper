# ModeKeeper — CLI contracts (artifacts + explain events)

| Command | Inputs | Artifacts (out_dir) | Explain events (cli.py) | Exit codes (happy / error) |
|---|---|---|---|
| `mk observe` | `--duration`, `--source synthetic|file|k8s`, `--path` (required for `file`), `--record-raw`, `--k8s-namespace`, `--k8s-deployment`, `--container`, `--out` | `explain.jsonl`; `observe_<timestamp>.json`; `observe_latest.json` | `observe_start`, `observe_source`, `observe_signals`, `observe_summary`, `observe_report`, `observe_stop` | `0` / argparse error (non-zero) |
| `mk demo run` | `--scenario`, `--out` | `explain.jsonl`; `demo_<timestamp>.json`; `demo_latest.json` | `demo_start`, `demo_report`, `demo_stop` | `0` / argparse error (non-zero) |
| `mk closed-loop run` | `--scenario`, `--k8s-namespace`, `--k8s-deployment`, `--observe-source synthetic|file|k8s`, `--observe-path`, `--observe-record-raw`, `--observe-duration`, `--observe-container`, `--out`, `--dry-run/--apply` | `explain.jsonl`; `closed_loop_<timestamp>.json`; `closed_loop_latest.json`; `summary.md`; `k8s_plan.json`; `k8s_plan.kubectl.sh`; when `--apply`: `k8s_verify_*.json`; `k8s_apply_*.json` (only if apply allowed); `closed_loop_latest.json` adds (when `--apply`): see section below | `closed_loop_observe_source`, `closed_loop_signals`, `closed_loop_proposed`, `k8s_plan_written`, `k8s_kubectl_plan_written`, `closed_loop_apply_result`, `closed_loop_apply_blocked`, `policy_decision`, `closed_loop_report` (+ `k8s_verify_*`, `k8s_apply_*` events when `--apply`) | `0` / argparse error (non-zero) |
| `mk closed-loop watch` | `--scenario`, `--k8s-namespace`, `--k8s-deployment`, `--observe-source synthetic|file|k8s`, `--observe-path`, `--observe-record-raw`, `--observe-duration`, `--observe-container`, `--interval`, `--max-iterations`, `--out`, `--dry-run/--apply` | `iter_0001/` etc (same as `closed-loop run`); `watch_latest.json`; `watch_summary.md` | (same events as `closed-loop run`, per iteration) | `0` / argparse error (non-zero) |
| `mk k8s render` | `--plan`, `--out` | `explain.jsonl`; `k8s_plan.kubectl.sh`; `k8s_render_<timestamp>.json`; `k8s_render_latest.json` | `k8s_render_start`, `k8s_kubectl_plan_written`, `k8s_render_report`; errors: `k8s_render_error` | `0` / `2` (plan read/parse/validate errors ⇒ only `explain.jsonl`, no render artifacts) |
| `mk k8s verify` | `--plan`, `--out`; env `KUBECTL` (optional) | `explain.jsonl`; `k8s_verify_<timestamp>.json`; `k8s_verify_latest.json` | `k8s_verify_start`, `k8s_verify_checked`, `k8s_verify_report`, `k8s_verify_diagnostic`; errors: `k8s_verify_error` | `0` / `2` (kubectl missing ⇒ `0` with report `ok=false`) |
| `mk k8s apply` | `--plan`, `--out`, `--force`; env `MODEKEEPER_PAID` | `explain.jsonl`; `k8s_apply_<timestamp>.json`; `k8s_apply_latest.json` (only when plan is valid) | `k8s_apply_start`, `k8s_apply_blocked`, `k8s_apply_report`, `k8s_apply_item_start`, `k8s_apply_item_result`; errors: `k8s_apply_error` | `0` (success) / `1` (apply failed) / `2` (blocked or plan errors; plan read/parse/validate errors ⇒ only `explain.jsonl`) |

## k8s_plan.kubectl.sh behavior

- Non-empty plan (items > 0): includes an informational header and may include `kubectl ...` lines.
- Empty plan (items == 0): kubectl-free (no `kubectl` substring), self-contained no-op.

## k8s_verify_diagnostic explain payload

- `name` and `error` are required; `namespace`, `rc`, `stderr`, and `detail` are optional.
- `namespace` is emitted for per-namespace `auth can-i` diagnostics (mixed-namespace plans).
- `diagnostics.auth_can_i_patch_deployments` and `diagnostics.auth_can_i_get_deployments` are bool|null (single-namespace plans only).
- `diagnostics.auth_can_i_patch_deployments_by_namespace` and `diagnostics.auth_can_i_get_deployments_by_namespace` are `{namespace: bool|null}`.
- Each `checks.items[*]` includes `auth_can_i_patch_deployments` / `auth_can_i_get_deployments` resolved per item.

## k8s_verify_latest.json verify_blocker

- `verify_blocker` is always present and nullable (null when `ok==true` or no blocker).
- Fields: `kind`, `index`, `namespace`, `name`, `detail` (index/namespace/name are null for non-item blockers).
- Deterministic priority when `ok==false`: kubectl_missing, namespace_missing (first missing), deployment_missing (first missing), rbac_denied (first attempted+failed with Forbidden/cannot patch), dry_run_failed (first attempted+failed), unknown.

## Raw observe recording fields

- `mk observe --record-raw PATH`: explain event `observe_source` includes `record_raw_path`, `record_raw_lines_written`, `record_raw_error`.
- `record_raw_error` is `null` on success; best-effort; `unsupported_source` when `--source synthetic`.
- `mk closed-loop run --observe-record-raw PATH`: explain event `closed_loop_observe_source` includes `record_raw_path`, `record_raw_lines_written`, `record_raw_error`.
- `closed_loop_latest.json` includes `observe_record_raw_path` and `observe_record_raw_lines_written` (null when not recording).
- `mk closed-loop watch --observe-record-raw PATH`: per-iteration `closed_loop_latest.json` includes `observe_record_raw_*`.
- `watch_latest.json` includes `observe_record_raw_path` and aggregated `observe_record_raw_lines_written`.

## watch_latest.json artifact_paths

- Watch report (`watch_latest.json`) includes `artifact_paths` (object) with: `watch_latest_path`, `watch_summary_path`, `last_iteration_report_path`, `last_iteration_explain_path`.
- Paths are strings; `last_iteration_*` are `null` when the corresponding artifact is missing.
- `watch_summary.md` renders pointer lines from `artifact_paths`; null values render as `null`.

## closed_loop_latest.json opportunity fields

- `opportunity_hours_est`, `opportunity_tokens_est`, `opportunity_usd_est` are included for all closed-loop runs (including dry-run/observe-only).
- `opportunity_assumptions` is an object with the cost model and formulas (e.g. `gpu_hour_usd`, `gpu_count`, `throughput_unit`, `baseline_window_s`, `opportunity_fraction`).
- `summary.md` mirrors the same fields for quick review.

## closed_loop_latest.json fields for --apply

- `verify_ok` (bool)
- `apply_attempted` (bool)
- `apply_ok` (bool, when attempted)
- `apply_blocked_reason` (string|null)
- `kill_switch_active` (bool)
- `kill_switch_signal` (safe string|null)
- `k8s_verify_report_path` (string path)
- `k8s_apply_report_path` (string path|null)
- invariant: `len(results) == len(proposed)` even when apply is blocked
- canonical kill-switch block reason: `kill_switch_active`

## schema_version / duration_s differences

- All commands (including `k8s verify`):
  - `schema_version`: `"v0"` (type: `str`)
  - `duration_s`: `int((finished_at - started_at).total_seconds())` (type: `int`, computed from datetime diff)

### mk passport observe-max

Free (observe-only) генерация propose-only паспорта и redacted отчёта рекомендаций.

Артефакты (в `--out <dir>`):
- `passport_observe_max_latest.json`
- `observe_max_latest.json`

Пример:
```bash
mk passport observe-max --observe-source file --observe-path <trace.jsonl> --out <outdir>
```
