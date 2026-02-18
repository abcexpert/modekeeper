# ModeKeeper Incident Playbooks

Dev setup: `docs/DEV_MINIKUBE_GPU.md`

## 1) Kill Switch (`MODEKEEPER_KILL_SWITCH`)

When `MODEKEEPER_KILL_SWITCH=1`, apply is blocked unconditionally.
Apply CLI entrypoints exit non-zero with a single-line error mentioning `MODEKEEPER_KILL_SWITCH`.

Checklist:
- Confirm env on runner: `echo "$MODEKEEPER_KILL_SWITCH"`
- Verify report fields:
  - `apply_blocked_reason == "kill_switch"` in `closed_loop_latest.json`
  - `block_reason == "kill_switch"` in `k8s_apply_latest.json`
- Keep kill switch enabled during incident triage to prevent any patch attempts.

Recovery:
- Remove or set `MODEKEEPER_KILL_SWITCH=0`.
- Re-run `mk k8s verify` first, then `mk k8s apply` (or one-shot `mk closed-loop run --apply`).

## 2) License Expired / Invalid

Symptoms:
- `block_reason` is one of:
  - `license_missing`
  - `license_expired`
  - `license_invalid`
  - `binding_mismatch`
  - `entitlement_missing`

Checklist:
- Run license validation:
  - `./.venv/bin/mk license verify --license ./license.json --out report/_license_verify`
- Inspect `report/_license_verify/license_verify_latest.json`:
  - `license_ok`
  - `reason`
  - `expires_at`
  - `entitlements_summary` (must include `apply`)
- Confirm runtime env points to the expected license path (`MODEKEEPER_LICENSE_PATH`).

Recovery:
- Replace/renew license, fix binding mismatch, or issue license with `apply` entitlement.
- Re-run verify/apply flow after `license_ok=true`.

## 3) RBAC Denied

Symptoms:
- Verify blocker `verify_blocker.kind == "rbac_denied"` or apply fails with RBAC-like stderr.
- `details.rbac` contains parsed denial context and hint.

Checklist:
- Inspect:
  - `k8s_verify_latest.json` -> `details.rbac`, `verify_blocker`, `diagnostics`
  - `k8s_apply_latest.json` -> `details.rbac`
- Use namespace-scoped permission checks:
  - `kubectl -n <ns> auth can-i get deployments`
  - `kubectl -n <ns> auth can-i patch deployments`
- Compare denial details (`user`, `verb`, `resource`, `api_group`, `namespace`) with current Role/RoleBinding.

Recovery:
- Grant least-privilege RBAC for `get` and `patch` on `deployments` in target namespace(s).
- Re-run `mk k8s verify` and confirm blocker is cleared before apply.

## 4) Rollback Workflow (`rollback_plan_latest.json`)

ModeKeeper writes rollback skeleton/plumbing artifacts for policy-bundle driven workflows.

Checklist:
- Locate:
  - `policy_bundle_latest.json`
  - `rollback_plan_latest.json`
- Confirm links in bundle under rollback metadata.
- Review rollback plan content before execution.

Suggested workflow:
1. Stop further applies (optionally set kill switch during incident).
2. Collect latest artifacts from run/apply output directory.
3. Inspect `rollback_plan_latest.json` and convert to explicit kubectl patch commands for your environment.
4. Execute rollback manually under change control.
5. Run `mk k8s verify` to validate post-rollback state.

Notes:
- Current rollback artifact is a controlled skeleton/plumbing step, not an automatic rollback executor.
