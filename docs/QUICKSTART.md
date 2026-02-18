# ModeKeeper Quickstart v0

This is the single recommended customer flow.

## 1) Install + command check

```bash
python3 -m pip install -U modekeeper
mk --help
```

Expected: `mk --help` exits with `0`.

## 2) Read-only onboarding (no cluster mutations)

```bash
mk observe --source synthetic --duration 30s --record-raw report/quickstart/observe/observe_raw.jsonl --out report/quickstart/observe
mk closed-loop run --scenario drift --observe-source synthetic --observe-duration 30s --dry-run --out report/quickstart/plan
PLAN="$(python3 -c 'import json; print(json.load(open("report/quickstart/plan/closed_loop_latest.json", encoding="utf-8"))["k8s_plan_path"])')"
mk k8s verify --plan "$PLAN" --out report/quickstart/verify
mk export bundle --in report/quickstart --out report/quickstart/export
```

This flow is verify-first and non-mutating (`observe`, `dry-run`, `verify`, `export` only).

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
