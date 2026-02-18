# ModeKeeper Quickstart v0

This is the single recommended customer flow.

## 1) Install + health check

```bash
./bin/mk-install
./bin/mk-doctor
```

Expected: `mk-doctor` returns `0` and reports PASS for all checks.

## 2) Read-only onboarding (no cluster mutations)

```bash
NS=default
DEPLOY=trainer
mk quickstart --k8s-namespace "$NS" --k8s-deployment "$DEPLOY" --out report/quickstart
```

This command is safe-by-default and does not run `kubectl patch`.

What it runs internally:

```bash
mk doctor
mk closed-loop run --scenario drift --k8s-namespace "$NS" --k8s-deployment "$DEPLOY" --dry-run --out report/quickstart/plan
PLAN="$(python3 -c 'import json; print(json.load(open("report/quickstart/plan/closed_loop_latest.json", encoding="utf-8"))["k8s_plan_path"])')"
mk k8s verify --plan "$PLAN" --out report/quickstart/verify
mk export bundle --in report/quickstart --out report/quickstart/export
```

## 3) Paid mode gate: verify license first

```bash
mk license verify --license ./license.json --out report/license_verify
```

Only proceed to apply if license verification is successful.

## 4) Apply prerequisites checklist (must all be true)

- `verify_ok=true` in the latest verify artifact.
- `MODEKEEPER_KILL_SWITCH` is not set to `1`.
- Valid paid license with apply entitlement is available.

Example paid apply run:

```bash
MODEKEEPER_LICENSE_PATH=./license.json mk closed-loop run --scenario drift --apply --out report/quickstart_apply
```
