# ModeKeeper CLI Reference

Source of truth: `src/modekeeper/cli.py` (`argparse`).

## Public execution model

- Entrypoint: `mk`
- Help: `mk --help`
- ModeKeeper CLI is customer-managed: commands run in your environment with your kubeconfig, permissions, and runtime controls.
- Recommended default is verify-first and strict read-only assessment: collect evidence, inspect plans, and review artifacts before any licensed apply path.
- `export handoff-pack` is the canonical review/handoff boundary for enterprise-facing artifact exchange.
- Public assessment path does not perform cluster mutation.

Top-level commands:
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
- with `--apply`, apply reports are written only when gate checks pass (for example: valid license, verify status, and cluster authorization)

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
- when `--apply` is requested but not authorized, reports remain explicit about blocked apply state

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

Use this command for generic bundle export and local packaging.

### `mk export handoff-pack`
Flags:
- `--in` (stored as `input_dir`, default: `report`)
- `--out` (default: `report/handoff_pack`)

Artifacts:
- `handoff_manifest.json`
- `handoff_pack.tar.gz`
- `handoff_summary.md`
- `handoff_pack.checksums.sha256`
- `HANDOFF_VERIFY.sh`
- `README.md`

Use this command as the canonical enterprise review/handoff pack boundary.

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

Apply is a licensed, gated path. For enterprise review flows, prefer `k8s render` + `k8s verify` first, then proceed to apply only when controls are satisfied.

## Public environment variables

- `KUBECTL`: kubectl binary path override.
- `KUBECONFIG`: kubeconfig path for cluster-scoped checks.
- `MODEKEEPER_LICENSE_PATH`: default license path.
- `MODEKEEPER_LICENSE_PUBLIC_KEYS_PATH`: public keyring path used in license verification.
- `MODEKEEPER_KILL_SWITCH`: customer-side safety stop (`1` blocks mutate/apply paths).

## Typical review-first sequence

```bash
mk observe --source file --path ./trace.jsonl --out ./report/observe
mk closed-loop run --dry-run --observe-source file --observe-path ./trace.jsonl --out ./report/run
mk k8s render --plan ./report/run/k8s_plan.json --out ./report/render
mk k8s verify --plan ./report/run/k8s_plan.json --out ./report/verify
mk export handoff-pack --in ./report --out ./report/handoff_pack
```

If your environment is licensed and approvals are complete, you can execute the apply path explicitly (for example `mk k8s apply` or `mk closed-loop run --apply`).
