# ModeKeeper CLI Contracts (Public)

Source of truth: `src/modekeeper/cli.py`.

This document defines public CLI/report contracts for enterprise-safe review.
Execution is customer-managed: commands run in your environment, with your kubeconfig and permissions.
Default posture is verify-first and strict read-only assessment.
Public assessment path does not perform cluster mutation.

## Public command contracts

| Command | Key inputs | Artifacts in `--out` | Explain events (stable family) | Exit codes |
|---|---|---|---|---|
| `mk observe` | `--duration`, `--source synthetic|file|k8s|k8s-logs`, `--path` (for file), `--record-raw`, `--k8s-namespace`, `--k8s-deployment`, `--container`, `--k8s-pod`, `--out` | `explain.jsonl`, `report_<timestamp>.json`, `observe_latest.json` | `observe_start`, `observe_source`, `observe_signals`, `observe_summary`, `observe_report`, `observe_stop` | `0` / non-zero on CLI/input errors |
| `mk demo run` | `--scenario`, `--out` | `explain.jsonl`, `demo_<timestamp>.json`, `demo_latest.json` | `demo_start`, `demo_report`, `demo_stop` | `0` / non-zero on CLI/input errors |
| `mk closed-loop run` | `--scenario`, `--k8s-namespace`, `--k8s-deployment`, `--observe-source synthetic|file|k8s|k8s-logs`, `--observe-path`, `--observe-record-raw`, `--observe-duration`, `--policy`, `--observe-container`, `--cooldown-s`, `--max-delta-per-step`, `--approve-advanced`, `--license-path`, `--dry-run/--apply`, `--out` | `explain.jsonl`, `closed_loop_<timestamp>.json`, `closed_loop_latest.json`, `summary.md`, `decision_trace_latest.jsonl`, `policy_bundle_latest.json`, `k8s_plan.json`, `k8s_plan.kubectl.sh`; with `--apply`: verify/apply reports and blocked-state fields when mutation is not authorized | `closed_loop_observe_source`, `closed_loop_signals`, `closed_loop_proposed`, `k8s_plan_written`, `k8s_kubectl_plan_written`, `closed_loop_apply_result`, `closed_loop_apply_blocked`, `policy_decision`, `closed_loop_report` (+ `k8s_verify_*`, `k8s_apply_*` families when `--apply`) | `0` / non-zero on CLI/input errors |
| `mk closed-loop watch` | `closed-loop run` inputs + `--interval`, `--max-iterations`, `--iterations` (legacy), `--out` | per-iteration `iter_0001/`... (same artifacts as `closed-loop run`), aggregate `watch_latest.json`, `watch_summary.md` | same event families as `closed-loop run`, emitted per iteration | `0` for normal completion; `2` when apply path is blocked by verify/license gates |
| `mk k8s render` | `--plan`, `--out` | `explain.jsonl`, `k8s_plan.kubectl.sh`, `k8s_render_<timestamp>.json`, `k8s_render_latest.json` | `k8s_render_start`, `k8s_kubectl_plan_written`, `k8s_render_report`; error family: `k8s_render_error` | `0` / `2` (plan read/parse/shape/validation errors) |
| `mk k8s verify` | `--plan`, `--out` (`KUBECTL` optional) | `explain.jsonl`, `k8s_verify_<timestamp>.json`, `k8s_verify_latest.json` | `k8s_verify_start`, `k8s_verify_checked`, `k8s_verify_report`, `k8s_verify_diagnostic`; error family: `k8s_verify_error` | `0` for completed verify report generation; `2` on plan read/parse/shape/validation errors |
| `mk k8s apply` | `--plan`, `--out`, `--force`, `--license-path` | `explain.jsonl`, `k8s_apply_<timestamp>.json`, `k8s_apply_latest.json` | `k8s_apply_start`, `k8s_apply_blocked`, `k8s_apply_report` (+ item-level events in licensed apply runtime) | Licensed apply path: `0` success / `1` apply failure / `2` blocked or preconditions failed. Public builds keep explicit blocked-state artifacts and do not mutate cluster state. |

## Verify-first and licensed apply boundary

- `--dry-run` and read-only commands are the default contract for assessment and review.
- `--apply` is a separate gated path requiring valid runtime preconditions (including license and verify checks).
- When apply is not authorized, reports remain explicit (`apply_blocked_reason`, `k8s_apply_latest.json`) and no mutation is performed.

## Export/handoff boundary

- `mk export handoff-pack` is the canonical enterprise review/handoff boundary.
- Contract artifacts: `handoff_manifest.json`, `handoff_pack.tar.gz`, `handoff_summary.md`, `handoff_pack.checksums.sha256`, `HANDOFF_VERIFY.sh`, `README.md`.

## Contracted report fields

### `k8s_plan.kubectl.sh`

- Non-empty plan (`items > 0`): informational header and one or more `kubectl` command lines.
- Empty plan (`items == 0`): kubectl-free no-op script.

### `k8s_verify_latest.json` diagnostics and blocker semantics

- `verify_blocker` is always present and nullable.
- `verify_blocker` fields: `kind`, `index`, `namespace`, `name`, `detail`.
- Deterministic blocker priority when `ok == false`:
  `kubectl_missing` -> `namespace_missing` -> `deployment_missing` -> `rbac_denied` -> `dry_run_failed` -> `unknown`.
- `k8s_verify_diagnostic` payload requires `name` and `error`; optional: `namespace`, `rc`, `stderr`, `detail`.
- `diagnostics.auth_can_i_patch_deployments` / `diagnostics.auth_can_i_get_deployments`: `bool|null` for single-namespace plans.
- `diagnostics.auth_can_i_patch_deployments_by_namespace` / `diagnostics.auth_can_i_get_deployments_by_namespace`: `{namespace: bool|null}` for mixed-namespace plans.
- Each `checks.items[*]` includes per-item `auth_can_i_patch_deployments` and `auth_can_i_get_deployments`.

### Raw observe recording fields

- `mk observe --record-raw PATH`: `observe_source` emits `record_raw_path`, `record_raw_lines_written`, `record_raw_error`.
- `mk closed-loop run/watch --observe-record-raw PATH`: `closed_loop_observe_source` and resulting reports carry the same fields.
- `record_raw_error` is best-effort and may be `unsupported_source` for synthetic input.
- `watch_latest.json` includes aggregated `observe_record_raw_lines_written`.

### `watch_latest.json` artifact pointers

- `artifact_paths` always includes:
  `watch_latest_path`, `watch_summary_path`, `last_iteration_report_path`, `last_iteration_explain_path`.
- Missing iteration artifacts are represented as `null`.
- `watch_summary.md` mirrors these pointers for human review.

### `closed_loop_latest.json` required fields

- Opportunity/value fields are always present for closed-loop runs:
  `opportunity_hours_est`, `opportunity_tokens_est`, `opportunity_usd_est`, `opportunity_assumptions`.
- Apply/verify state fields (including blocked states):
  `verify_ok`, `apply_attempted`, `apply_ok`, `apply_blocked_reason`, `kill_switch_active`, `kill_switch_signal`, `k8s_verify_report_path`, `k8s_apply_report_path`.
- Invariant: `len(results) == len(proposed)` even when apply is blocked.
- Canonical kill-switch block reason: `kill_switch_active`.

### Shared report metadata

- `schema_version` is `"v0"`.
- `duration_s` is integer wall-clock seconds (`int((finished_at - started_at).total_seconds())`).

## `mk passport observe-max` (public free path)

Read-only observe-max contract (propose-only passport + redacted recommendations report).

Artifacts in `--out`:
- `passport_observe_max_latest.json`
- `observe_max_latest.json`

Example:

```bash
mk passport observe-max --observe-source file --observe-path <trace.jsonl> --out <outdir>
```
