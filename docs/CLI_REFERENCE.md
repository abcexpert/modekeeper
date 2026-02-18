# ModeKeeper CLI Reference

Source of truth: `src/modekeeper/cli.py` (`argparse`).

## Entrypoint
- Command: `mk`
- Global flag: `--version`
- Help: `mk --help`

Top-level commands:
- `doctor`
- `quickstart`
- `eval`
- `observe`
- `closed-loop`
- `demo`
- `fleet`
- `roi`
- `export`
- `chords`
- `passport`
- `license`
- `k8s`

## Commands and flags

### `mk doctor`
Flags:
- none

Behavior:
- checks local prerequisites (python/mk/kubectl/kubeconfig readability)
- prints PASS/FAIL lines

Artifacts:
- none (stdout/stderr only)

### `mk quickstart`
Flags:
- `--out` (default: `report/quickstart_<UTC ts>`)
- `--k8s-namespace` (default: `default`)
- `--k8s-deployment` (default: `trainer`)
- `--scenario` (default: `drift`)
- `--observe-source` (`synthetic|file|k8s|k8s-logs`, default: `synthetic`)
- `--observe-path`
- `--observe-duration` (default: `60s`)
- `--observe-container` (default: `auto`)
- `--policy` (`chord|scalar`, default: `chord`)

Artifacts under `<out>/`:
- `doctor/doctor.json`
- `doctor/summary.md`
- `plan/closed_loop_latest.json`
- `plan/closed_loop_<ts>.json`
- `plan/summary.md`
- `plan/k8s_plan.json`
- `plan/k8s_plan.kubectl.sh`
- `plan/decision_trace_latest.jsonl`
- `plan/policy_bundle_latest.json`
- `verify/k8s_verify_latest.json`
- `verify/k8s_verify_<ts>.json`
- `verify/explain.jsonl`
- `export/bundle_manifest.json`
- `export/bundle.tar.gz`
- `export/bundle_summary.md`
- `summary.md`

### `mk eval file`
Flags:
- `--path` (required)
- `--policy` (`chord|scalar`, default: `chord`)
- `--out` (default: `report`)

Artifacts:
- `eval_latest.json`
- `eval_summary.md`
- `explain.jsonl`

### `mk eval k8s`
Flags:
- `--k8s-namespace` (default: `default`)
- `--k8s-deployment` (default: `trainer`)
- `--container` (default: `auto`)
- `--observe-duration` (default: `60s`)
- `--policy` (`chord|scalar`, default: `chord`)
- `--out` (default: `report`)

Artifacts:
- `eval_latest.json`
- `eval_summary.md`
- `explain.jsonl`
- `k8s_plan.json`
- `k8s_plan.kubectl.sh`
- `k8s_verify_latest.json`
- `k8s_verify_<ts>.json`

### `mk observe`
Flags:
- `--duration` (default: `10m`; supports `ms|s|m|h`)
- `--source` (`synthetic|file|k8s|k8s-logs`, default: `synthetic`)
- `--path`
- `--record-raw`
- `--k8s-namespace` (default: `default`)
- `--k8s-deployment` (default: `trainer`)
- `--container` (default: `auto`)
- `--out` (default: `report`)

Artifacts:
- `report_<ts>.json`
- `observe_latest.json`
- `explain.jsonl`

### `mk closed-loop run`
Flags:
- `--out` (default: `report`)
- `--scenario` (default: `drift`)
- `--k8s-namespace` (default: `default`)
- `--k8s-deployment` (default: `trainer`)
- `--observe-source` (`synthetic|file|k8s|k8s-logs`, default: `synthetic`)
- `--observe-path`
- `--observe-record-raw`
- `--observe-duration` (default: `60s`)
- `--policy` (`chord|scalar`, default: `chord`)
- `--observe-container` (default: `auto`)
- `--cooldown-s` (default: `30`)
- `--max-delta-per-step` (default: `0`)
- `--approve-advanced` (flag)
- `--license-path`
- `--dry-run | --apply` (mutually exclusive)

Artifacts:
- `closed_loop_<ts>.json`
- `closed_loop_latest.json`
- `summary.md`
- `decision_trace_latest.jsonl`
- `policy_bundle_latest.json`
- `k8s_plan.json`
- `k8s_plan.kubectl.sh`
- `explain.jsonl`
- apply-requested path additionally emits `k8s_apply_latest.json` / `k8s_apply_<ts>.json` with gate/apply result

### `mk closed-loop watch`
Flags:
- `--out` (required)
- `--scenario` (required)
- `--k8s-namespace` (default: `default`)
- `--k8s-deployment` (default: `trainer`)
- `--observe-source` (`synthetic|file|k8s|k8s-logs`, default: `synthetic`)
- `--observe-path`
- `--observe-record-raw`
- `--observe-duration` (default: `60s`)
- `--policy` (`chord|scalar`, default: `chord`)
- `--observe-container` (default: `auto`)
- `--cooldown-s` (default: `30`)
- `--max-delta-per-step` (default: `0`)
- `--approve-advanced` (flag)
- `--license-path`
- `--iterations` (default: `0`, legacy)
- `--interval` (default: `30s` as milliseconds internally)
- `--max-iterations` (default: unlimited)
- `--dry-run | --apply` (mutually exclusive)

Artifacts under `<out>/`:
- per iteration: `iter_0001/`, `iter_0002/`, ... with same files as `closed-loop run`
- aggregate: `watch_latest.json`, `watch_summary.md`
- apply-requested path emits watch summary with blocked reason in public runtime

### `mk demo run`
Flags:
- `--scenario` (default: `drift`)
- `--out` (default: `report`)

Artifacts:
- `demo_<ts>.json`
- `demo_latest.json`
- `explain.jsonl`

### `mk demo mk068`
Flags:
- `--out` (default: `report`)

Artifacts:
- written by `run_mk068_demo(out_dir=...)` into provided output directory

### `mk fleet inventory`
Flags:
- `--contexts` (comma-separated)
- `--context` (repeatable)
- `--out` (default: `report/_inventory`)

Artifacts:
- `inventory_latest.json`

### `mk fleet policy`
Flags:
- `--policy` (required)
- `--contexts` (comma-separated)
- `--context` (repeatable)
- `--out` (default: `report/_policy_propagation`)

Artifacts:
- `policy_propagation_latest.json`

### `mk roi mk074`
Flags:
- `--observe-source` (`file|k8s|k8s-logs`, required)
- `--observe-path`
- `--k8s-namespace` (default: `default`)
- `--k8s-deployment` (default: `trainer`)
- `--observe-container` (default: `auto`)
- `--observe-duration` (default: `60s`)
- `--out` (required)

Artifacts:
- `mk074_before_latest.json`
- `mk074_after_latest.json`
- `mk074_before_after_latest.json`

### `mk roi estimate`
Flags:
- `--observe-source` (`file`, required)
- `--observe-path` (required)
- `--out` (default: `report/_roi_estimate`)

Artifacts:
- `roi_estimate_latest.json`

### `mk roi report`
Flags:
- `--preflight` (default: `report/preflight/preflight_latest.json`)
- `--eval` (default: `report/eval_k8s/eval_latest.json`)
- `--watch` (default: `report/watch_k8s/watch_latest.json`)
- `--out` (default: `report/roi`)

Artifacts:
- `roi_latest.json`
- `roi_summary.md`
- `explain.jsonl`

### `mk export bundle`
Flags:
- `--in` (stored as `input_dir`, default: `report`)
- `--out` (default: `report/bundle`)

Artifacts:
- `bundle_manifest.json`
- `bundle.tar.gz`
- `bundle_summary.md`

### `mk chords validate`
Flags:
- `--catalog` (required)
- `--out` (default: `report/_chords_validate`)

Artifacts:
- `chords_validate_latest.json`

### `mk passport templates`
Flags:
- none

Behavior:
- prints built-in template names

### `mk passport show`
Flags:
- `--template` (required)

Behavior:
- prints selected template JSON

### `mk passport validate`
Flags:
- `--file` (required)

Behavior:
- validates passport file

### `mk passport observe-max`
Flags:
- `--observe-source` (`file|k8s|k8s-logs`, required)
- `--observe-path`
- `--k8s-namespace` (default: `default`)
- `--k8s-deployment` (default: `trainer`)
- `--observe-container` (default: `auto`)
- `--observe-duration` (default: `60s`)
- `--out` (required)

Artifacts:
- `passport_observe_max_latest.json`
- `observe_max_latest.json`

### `mk passport observe-max-report`
Flags:
- same as `passport observe-max`

Artifacts:
- `observe_max_latest.json`

### `mk license verify`
Flags:
- `--license` (default resolution: `MODEKEEPER_LICENSE_PATH`, else `${HOME}/.config/modekeeper/license.json`)
- `--out` (default: `report/_license_verify`)
- `--kubectl` (default: `kubectl`)

Artifacts:
- `license_verify_latest.json`

### `mk k8s render`
Flags:
- `--plan` (required)
- `--out` (default: `report`)

Artifacts:
- `k8s_plan.kubectl.sh`
- `k8s_render_<ts>.json`
- `k8s_render_latest.json`
- `explain.jsonl`

### `mk k8s verify`
Flags:
- `--plan` (required)
- `--out` (default: `report`)

Artifacts:
- `k8s_verify_<ts>.json`
- `k8s_verify_latest.json`
- `explain.jsonl`

### `mk k8s preflight`
Flags:
- `--k8s-namespace` (default: `default`)
- `--k8s-deployment` (default: `trainer`)
- `--out` (default: `report/preflight`)

Artifacts:
- `preflight_latest.json`
- `preflight_summary.md`
- `explain.jsonl`

### `mk k8s apply`
Flags:
- `--plan` (required)
- `--out` (default: `report`)
- `--force` (reserved)
- `--license-path`

Artifacts:
- `k8s_apply_<ts>.json`
- `k8s_apply_latest.json`
- `explain.jsonl`
- `policy_bundle_latest.json`

## Important env vars used by CLI
- `KUBECTL`: kubectl binary path override.
- `KUBECONFIG`: kubeconfig path (doctor/preflight context checks).
- `MODEKEEPER_GPU_HOUR_USD`, `MODEKEEPER_GPU_COUNT`: cost model overrides for value/opportunity math.
- `MODEKEEPER_KILL_SWITCH`: absolute apply/mutate block when `1`.
- `MODEKEEPER_LICENSE_PATH`: license path resolution fallback.
- `MODEKEEPER_LICENSE_PUBLIC_KEYS_PATH`: keyring file override for license verification.
- `MODEKEEPER_INTERNAL_OVERRIDE`, `MODEKEEPER_PAID`: internal override path used in gating logic.

