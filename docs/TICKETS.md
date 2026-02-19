# Tickets


- ID: MK-112
  Title: PyPI landing README + enterprise quickstart (install, eval, observe, closed-loop gating)
  Status: DONE
  DoD:
    - README starts with a crisp 5–8 line value prop (what it is, who it’s for, why safe).
    - Install section: `python -m pip install -U modekeeper` and optional `pipx install modekeeper`.
    - Quickstart section:
      - `mk --help`
      - `mk doctor`
      - `mk eval ...` (read-only customer-safe)
      - `mk observe ...` (OBSERVE_ONLY)
      - `mk closed-loop ...` clearly marked as licensed + safety gates (kill-switch, approval).
    - “How it works” (high-level): observe → propose → verify → apply (when licensed), with artifacts.
    - Support/Contact/Commercial CTA stub (enterprise): how to request license / pilots.
  Acceptance criteria:
    - PyPI page clearly positions Free vs Paid:
      - Free = customer-safe read-only (`doctor`/`quickstart`/`observe`/`eval`/`roi`/`plan`/`verify`/`export`), no mutations.
      - Paid = `apply` + advanced chords + fleet/governance + enterprise policy packs, gated by license + kill-switch + `verify_ok`.
    - PyPI description does not suggest dev-only flows (no editable installs) and references one-command onboarding: `mk quickstart --out ...` (read-only).
    - Public PyPI artifacts policy is explicit: do not ship full proprietary core on PyPI; PyPI package is a stub/safe agent only.
  Evidence:
    - commit: 4d589c9
    - verification: rm -rf /tmp/mk_qs_probe && PYTHONPATH=src python -m modekeeper.cli quickstart --out /tmp/mk_qs_probe && test -f /tmp/mk_qs_probe/plan/decision_trace_latest.jsonl


- ID: MK-113
  Title: Commercial distribution & IP posture (open-core)
  Priority: MUST
  Status: DONE
  Scope:
    - Split distribution into:
      - public PyPI package (`modekeeper`): safe-only stub/agent (read-only surface)
      - private paid package (`modekeeper-pro` or similar): apply/advanced/fleet/governance/policy packs
    - Installer behavior:
      - `mk-install` pro install is best-effort; license-gate failures never block public install.
      - `mk-install` falls back to repo-pro when gate/pro index is unavailable.
      - `mk-install` network errors/timeouts are user-facing warnings without traceback and include root cause (example: `HTTP 403: license_invalid`).
    - Release gates:
      - ensure PyPI uploads contain no paid core; ideally upload wheel-only; never upload sdist once stub is in place.
    - Documentation:
      - update `WORKFLOW` to show Install -> Doctor -> Quickstart (free) -> License enable -> Pro install -> Apply.
      - add `tools/systemd/*` templates and `docs/GETTING_STARTED.md` section G for systemd setup.
    - License-gate server:
      - support `GET /healthz`.
      - support `MK_LICENSE_GATE_PUBLIC_KEYS_PATH`.
      - use `mc share download`.
      - run as systemd service on an internal deployment host.
  Acceptance criteria:
    - Without license: any apply path is blocked with a clear reason artifact; quickstart remains read-only.
    - With license: pro package enables apply path (still gated by kill-switch + `verify_ok`).
    - CI/release checks prevent accidental publishing of paid core to PyPI.
    - `mk-install` can install stub-only and (when licensed) install pro, with best-effort pro path that never blocks public install.
  Evidence:
    - commit: `beefe3e` (install: license-gate best-effort + repo-pro fallback + no tracebacks)
    - commit: `d686490` (install: better network errors + gate: keys path + healthz; docs)
    - commit: `8498613` (docs/templates: systemd templates + reproducible setup; docs fixes)
    - verification: `pytest -q tests/test_mk_install.py` (green)
    - verification: `python3 -m py_compile tools/mk_license_gate_server.py` (green)
    - commit: `817aa61` (install: surface license-gate HTTP errors in warning; test 403 license_invalid)


- ID: MK-111
  Title: Publish ModeKeeper to PyPI so ./bin/mk-install works out-of-the-box
  Status: DONE
  DoD:
    - Add `docs/RELEASE.md` with one recommended release flow: bump version, `python -m build`, and `twine upload dist/*`.
    - Release flow requires `TWINE_USERNAME=__token__` and `TWINE_PASSWORD` from environment; no secrets are stored in repo.
    - `pyproject.toml` is PyPI-ready: `name = "modekeeper"`, SemVer `version`, README included as project readme, and `mk` console entrypoint verified.
    - Sandbox validation passed: `python -m build` succeeds and installing `dist/*.whl` in a fresh venv provides `mk --help`.

  Evidence (2026-02-15):
    - pypi: https://pypi.org/project/modekeeper/0.1.1/
    - commit: 9fcb033
    - twine_check: PASS
    - install_from_pypi: pip install -U modekeeper

- ID: MK-109
  Title: mk-install wheel selection + quickstart plan path derivation
  Status: DONE
  DoD:
    - `bin/mk-install` fetches PyPI JSON once (`/pypi/modekeeper/json`) and computes "latest" as the highest PEP440 version in `releases` that has at least one wheel entry with both `.whl` filename and URL.
    - When multiple wheels exist for that version, `bin/mk-install` prefers `py3-none-any.whl` when present.
    - `bin/mk-install` installs via direct wheel URL: `pip install -U --no-cache-dir <wheel_url>` (avoids stale `/simple` index responses).
    - `docs/QUICKSTART.md` no longer hardcodes `report/quickstart_plan/k8s_plan.json`; it derives `PLAN` from `report/quickstart_plan/closed_loop_latest.json` using `python3` and passes `--plan "$PLAN"` to verify.

- ID: MK-108
  Title: Customer-ready onboarding v0 (install + doctor + quickstart)
  Status: DONE
  DoD:
    - Add `bin/mk-install` for normal-user install without repo checkout:
      - creates/updates `~/.modekeeper/venv` idempotently
      - installs package via wheel (non-editable)
      - creates `~/.local/bin/mk` symlink/script or prints exact PATH instructions if unavailable
      - installs into `~/.modekeeper/venv` and refreshes `~/.local/bin/mk` symlink
      - online default: fetches PyPI JSON once, selects the highest PEP440 release with a wheel URL (prefers `py3-none-any.whl`), then installs via `python -m pip install -U --no-cache-dir <wheel_url>`
      - offline CI/tests: if `MODEKEEPER_WHEEL` is set, installs that wheel path instead
      - prints next steps: `mk doctor`, `mk --help`
      - non-interactive and safe-by-default (no cluster mutations)
    - Add `bin/mk-doctor` checks with PASS/FAIL + hints:
      - python3 present
      - venv exists
      - mk runnable
      - kubectl present
      - kubeconfig readable
      - exit `0` when all pass, otherwise `2`
    - Add `docs/QUICKSTART.md` with one recommended flow:
      - install
      - read-only plan/verify/watch
      - license verify (paid)
      - apply prerequisites (`verify_ok=true`, kill-switch off)
    - Update `docs/WORKFLOW.md` to point to quickstart and mark `./bin/mk-demo-sales` as dev/WSL oriented.

- ID: MK-099
  Title: Kill-switch absolute
  Status: DONE
  Acceptance criteria:
    - (a) `MODEKEEPER_KILL_SWITCH=1` blocks any apply/mutate path unconditionally (internal override cannot bypass)
    - (b) apply CLI entrypoints return non-zero with single-line error mentioning `MODEKEEPER_KILL_SWITCH`
    - (c) targeted kill-switch tests pass
  Evidence stub:
    - tests: `pytest -q -k kill_switch`
    - artifacts: `docs/evidence/mk099/` (reserved)

- ID: MK-100
  Title: Licensing v1 (kid + entitlements + offline activation)
  Status: DONE
  Acceptance criteria:
    - (a) key management: allowlist file `{kid -> public_key}` + verify selects key by `kid`; unknown `kid` => `license_invalid`; rotation via allowlist edit only
    - (b) entitlements: free mode read-only (`plan/verify/watch`), paid mode enables `apply/autotune`; enforced at CLI apply entrypoints and mutation gate layer; kill-switch remains absolute
    - (c) offline activation lookup order is canonical and deterministic: `--license-path` > `MODEKEEPER_LICENSE_PATH` > `./modekeeper.license.json`
    - (d) apply commands print single-line clear errors for `license_missing` / `license_invalid` when apply is requested
    - (e) focused tests cover license_missing, valid+kill_switch precedence, and unknown kid => `license_invalid`
  Evidence stub:
    - tests: `pytest -q -k "license or entitlement"`
    - key allowlist: `src/modekeeper/license/public_keys.json`
    - docs: `docs/WORKFLOW.md`

- ID: MK-105
  Title: One-command safety gates demo (non-mutating)
  Status: DONE
  DoD:
    - Add `bin/mk-demo-safety-gates` (default out: `report/_demo_safety_gates`) that runs without cluster mutations.
    - Script writes a local minimal `plan.json` (same schema as `mk k8s apply` tests).
    - Script records per-case artifacts in subdirs and prints one-line summary `case_name rc reason`.
    - Covered cases: A) missing license path -> `license_invalid`; B) unknown `kid` -> `license_invalid`; C) failing verify artifact (`verify_ok=false`) -> `verify_failed` by core `mk k8s apply`; D) kill-switch -> `kill_switch` with `rc=2` and fixed stderr line.
    - Script exits non-zero if any case does not match expected `rc`/reason.
    - `docs/WORKFLOW.md` includes a short "One-command safety gates demo (non-mutating)" section.

- ID: MK-106
  Title: One-command full sales demo (guardrails + real drift/apply)
  Status: DONE
  DoD:
    - Add `bin/mk-demo-sales` for local developer machines (including WSL), with no remote server assumptions.
    - Script runs `./bin/mk-demo-safety-gates` (default out) and then `./bin/mk-demo-k8s-drift` (default behavior).
    - Script prints a short header before each stage.
    - Script exits non-zero if any stage fails.
    - Final output includes safety artifacts path `report/_demo_safety_gates` and drift/apply artifacts paths `report/_license_dev_verify` + `report/_cl_k8s_apply_paid`.

- ID: MK-107
  Title: mk-demo-sales CLI polish (keep-flag passthrough + help/usage)
  Status: DONE
  DoD:
    - `bin/mk-demo-sales` parses `--keep-license`, `--keep-deploy`, `-h/--help`; unknown args print usage and exit `2`.
    - Keep flags are passed through to `./bin/mk-demo-k8s-drift`; default remains safe (no keep flags unless explicitly set).
    - Preflight checks require `.venv/bin/mk` and `.venv/bin/python`; missing venv prints a clear developer-machine/WSL message and exits `2`.
    - Final summary lines remain unchanged:
      - `safety artifacts: report/_demo_safety_gates`
      - `drift/apply artifacts: report/_license_dev_verify report/_cl_k8s_apply_paid`

- ID: MK-104
  Title: Make verify_ok=true a hard prerequisite for ALL apply/mutate entrypoints
  Status: DONE
  DoD:
    - Any apply/mutate entrypoint (`mk k8s apply`, `mk closed-loop run --apply`, `mk closed-loop watch --apply`, and shared apply helper paths to `kubectl patch`) blocks unless `verify_ok=true`.
    - Missing verify report blocks with `verify_missing`; verify `ok=false` (or any non-true) blocks with `verify_failed`.
    - Verify-gate block behavior is deterministic: `exit code 2`, fixed one-line stderr `ERROR: verify_ok=true is required for apply/mutate operations`, and `k8s_apply_latest.json` is still written with stable `block_reason`/`reason`.
    - Precedence is explicit: kill-switch wins first; verify gate still blocks even with valid license.
    - Focused tests cover missing/failed verify for `mk k8s apply`, closed-loop apply verify-block behavior, non-mutating closed-loop regression, and kill-switch precedence remains green.

- ID: MK-001
  Title: Align k8s verify report schema_version/duration_s with v0 report contract
  Status: DONE
  Acceptance criteria:
    - (a) verify report schema_version=="v0" (str)
    - (b) duration_s int(datetime diff)
    - (c) pytest -q green
    - (d) docs updated.

- ID: MK-002
  Title: Implement real k8s apply (kubectl patch) under paid license after verify-ok
  Status: DONE
  Acceptance criteria:
    - (a) paid+verify-ok or --force выполняет kubectl patch
    - (b) rc 0/1/2 как описано
    - (c) pytest -q зелёный
    - Verified on kind (CPU): verify ok=true, apply rc=0, annotations updated

- ID: MK-003
  Title: Add trainer-minimal manifest with annotation-driven knobs
  Status: DONE

- ID: MK-004
  Title: Canonical kind/e2e bootstrap + docs entrypoint
  Status: DONE

- ID: MK-005
  Title: Implement full pipeline for closed-loop --apply (verify + policy + apply)
  Status: DONE

- ID: MK-007
  Title: Make canonical paid e2e path explicit and add smoke script
  Status: DONE

- ID: MK-008
  Title: Add paid apply e2e script and docs
  Status: DONE

- ID: MK-009
  Title: Fix closed-loop apply booleans (apply_attempted/apply_ok)
  Status: DONE

- ID: MK-010
  Title: Polish e2e scripts output; quiet dev-shell; filter terminating pods
  Status: DONE

- ID: MK-012
  Title: Improve summary.md for closed-loop --apply status
  Status: DONE

- ID: MK-014
  Title: Polish CLI_CONTRACTS readability for closed-loop --apply fields
  Status: DONE

- ID: MK-015
  Title: Align README with canonical kind/e2e docs + scripts
  Status: DONE

- ID: MK-016
  Title: Fix README alignment with canonical kind/e2e (remove contradictions and duplication)
  Status: DONE

- ID: MK-017
  Title: Docs: clarify k8s_apply_latest.json items live under .checks.items
  Status: DONE

- ID: MK-018
  Title: UX: add top-level .items alias to k8s_apply_latest.json (checks.items)
  Status: DONE

- ID: MK-019
  Title: Add closed-loop watch controller (continuous loop) with session artifacts
  Status: DONE

- ID: MK-020
  Title: K8s-backed observe source + closed-loop wiring (run/watch) for real signals
  Status: DONE

- ID: MK-021
  Title: Trainer: emit telemetry JSONL for k8s observe (ts + step_time_ms)
  Status: DONE

- ID: MK-022
  Title: Trainer: step_time_ms depends on concurrency/prefetch knobs for deterministic k8s feedback loop
  Status: DONE

- ID: MK-023
  Title: Trainer: emit bursty step_time_ms when knobs are low to exercise latency_burst
  Status: DONE

- ID: MK-024
  Title: Fix trainer-minimal.yaml: env wiring for concurrency/prefetch so k8s feedback loop converges after apply
  Status: DONE

- ID: MK-025
  Title: Skip noop apply when no proposals + fix watch rollup applied_total
  Status: DONE

- ID: MK-026
  Title: Fix dry_run flag semantics for apply_skipped (CLI --apply vs --dry-run)
  Status: DONE

- ID: MK-027
  Title: Persist apply_requested/dry_run in reports (avoid null/missing fields)
  Status: DONE

- ID: MK-028
  Title: Report dry_run reflects CLI flag for apply/no-proposals
  Status: DONE

- ID: MK-029
  Title: watch_summary includes dry_run/apply totals
  Status: DONE

- ID: MK-030
  Title: Add MVP v0 Definition of Done doc and reference it from SNAPSHOT
  Status: DONE
  Acceptance criteria:
    - (a) `docs/DEFINITION_OF_DONE.md` defines MVP v0 DoD with checklist + smoke commands
    - (b) `docs/SNAPSHOT.md` points to the DoD and includes a short summary

- ID: MK-031
  Title: Make noop k8s_plan.kubectl.sh kubectl-free when items==0
  Status: DONE
  Acceptance criteria:
    - (a) when plan items==0, k8s_plan.kubectl.sh contains no 'kubectl' lines
    - (b) watch tests cover apply/no-proposals and dry-run/no-proposals cases
    - (c) pytest -q green

- ID: MK-032
  Title: Tests harden empty-plan kubectl-free at render level
  Status: DONE

- ID: MK-033
  Title: Docs: clarify k8s_plan.kubectl.sh behavior for empty vs non-empty plans
  Status: DONE
  Acceptance criteria:
    - (a) CLI_CONTRACTS documents non-empty plan includes informational header and may include kubectl lines
    - (b) CLI_CONTRACTS documents empty plan is kubectl-free (no 'kubectl' substring) and a self-contained no-op
    - (c) pytest -q green

- ID: MK-034
  Title: k8s verify richer diagnostics (kubectl/server version + RBAC signal)
  Status: DONE
  Acceptance criteria:
    - (a) k8s_verify_latest.json includes diagnostics.kubectl_version/server_version/auth_can_i_patch_deployments (nullable)
    - (b) diagnostics are best-effort; failures emit explain.jsonl diagnostic events
    - (c) verify tests cover diagnostics keys and pytest -q green

- ID: MK-035
  Title: verify diagnostics: namespace_unavailable is explicit and tested
  Status: DONE

- ID: MK-036
  Title: Tests: ensure no kubectl auth can-i call on mixed namespace
  Status: DONE

- ID: MK-037
  Title: Docs: CLI_CONTRACTS explain events for verify diagnostics
  Status: DONE
  Acceptance criteria:
    - (a) CLI_CONTRACTS mk k8s verify row lists k8s_verify_diagnostic explain event
    - (b) CLI_CONTRACTS documents k8s_verify_diagnostic payload fields (name/error required; rc/stderr/detail optional)
    - (c) pytest -q green

- ID: MK-038
  Title: verify diagnostics: add RBAC signal for get deployments
  Status: DONE
  Acceptance criteria:
    - (a) verify diagnostics include auth_can_i_get_deployments (nullable)
    - (b) namespace_unavailable is emitted for mixed/empty namespace
    - (c) tests cover auth can-i patch/get booleans and pytest -q green

- ID: MK-039
  Title: Docs: verify diagnostics fields updated
  Status: DONE
  Acceptance criteria:
    - (a) CLI_CONTRACTS mentions auth_can_i_patch_deployments/auth_can_i_get_deployments diagnostics fields
    - (b) pytest -q green

- ID: MK-040
  Title: k8s verify: first-blocker UX
  Status: DONE
  Acceptance criteria:
    - (a) k8s_verify reports include verify_blocker (nullable) with deterministic priority
    - (b) tests cover verify_blocker presence and failing scenario index
    - (c) pytest -q green

- ID: MK-041
  Title: Docs: document verify_blocker in CLI_CONTRACTS
  Status: DONE
  Acceptance criteria:
    - (a) CLI_CONTRACTS documents verify_blocker presence, fields, and priority
    - (b) pytest -q green

- ID: MK-042
  Title: Record/replay workflow + golden traces
  Status: DONE
  Acceptance criteria:
    - (a) docs playbook covers k8s record and file replay workflow
    - (b) golden observe traces added under tests/data/observe
    - (c) tests replay traces via closed-loop run/watch with invariants
    - (d) pytest -q green

- ID: MK-043
  Title: Record/replay tests for sparse and out-of-order traces
  Status: DONE
  Acceptance criteria:
    - (a) tests run closed-loop replay for sparse.jsonl and out_of_order.jsonl
    - (b) assertions cover rc==0, latest report artifacts, schema_version v0, duration_s int
    - (c) out_of_order trace does not crash; stable trace allows zero proposals
    - (d) pytest -q green

- ID: MK-044
  Title: Record/replay robustness without k8s/GPU
  Status: DONE
  Acceptance criteria:
    - (a) observe-source=file drops blank/invalid/invalid-shape/missing-field records without crashing
    - (b) observe_ingest counters persisted in closed_loop_latest.json and explain payloads
    - (c) corrupted/duplicates/clock_skew traces added under tests/data/observe
    - (d) record/replay tests cover dirty traces and corrupted drop counter
    - (e) pytest -q green

- ID: MK-045
  Title: Aggregate observe_ingest in closed-loop watch
  Status: DONE
  Acceptance criteria:
    - (a) watch_latest.json aggregates observe_ingest counters across iterations
    - (b) watch_summary.md includes observe_ingest totals when present
    - (c) tests cover corrupted.jsonl closed-loop watch rollup and artifacts
    - (d) pytest -q green

- ID: MK-046
  Title: UX: watch_summary pointers to last iteration artifacts
  Status: DONE
  Acceptance criteria:
    - (a) watch_summary.md includes paths to watch_latest.json and last-iteration report/explain artifacts
    - (b) tests cover these lines and pytest -q green

- ID: MK-047
  Title: watch_latest.json artifact pointers
  Status: DONE
  Acceptance criteria:
    - (a) watch_latest.json includes artifact_paths with watch_latest_path, watch_summary_path, last_iteration_report_path, last_iteration_explain_path
    - (b) last_iteration_* fields are null when missing
    - (c) corrupted watch replay test asserts rc==0, artifacts exist, and paths match expected
    - (d) pytest -q green

- ID: MK-048
  Title: keep watch_summary pointers consistent with watch_latest artifact_paths
  Status: DONE
  Acceptance criteria:
    - (a) watch_summary.md renders pointer lines from artifact_paths when present
    - (b) null pointer values render as "null" in watch_summary.md
    - (c) tests cover null last_iteration_* pointers
    - (d) pytest -q green

- ID: MK-049
  Title: Docs: document watch_latest.json artifact_paths
  Status: DONE
  Acceptance criteria:
    - (a) CLI_CONTRACTS documents watch_latest.json artifact_paths fields and null semantics
    - (b) pytest -q green

- ID: MK-050
  Title: Sanity: watch artifact_paths match watch_summary pointers
  Status: DONE
  Acceptance criteria:
    - (a) closed-loop watch run (replay corrupted.jsonl) produces watch_latest.json with artifact_paths
    - (b) watch_summary.md pointer lines match watch_latest.json artifact_paths
    - (c) pytest -q green

- ID: MK-051
  Title: Record/replay: realistic dirty trace + watch test
  Status: DONE
  Acceptance criteria:
    - (a) add tests/data/observe/realistic_dirty.jsonl (duplicates/out-of-order/clock-skew + invalid lines)
    - (b) add closed-loop watch replay test with rc==0, artifacts exist, observe_ingest.dropped_total > 0
    - (c) pytest -q green

- ID: MK-052
  Title: Observe raw recorder for replay
  Status: DONE
  Acceptance criteria:
    - (a) observe/closed-loop CLI support raw recorder flags
    - (b) explain payloads include record_raw_* fields
    - (c) reports persist observe_record_raw_* fields with watch aggregation
    - (d) tests cover closed-loop watch raw recording
    - (e) pytest -q green

- ID: MK-053
  Title: Snapshot refresh + roadmap; docs consistent with current code
  Status: DONE
  Acceptance criteria:
    - (a) SNAPSHOT updated with DONE/NEXT sections
    - (b) CLI_CONTRACTS consistent with current CLI/report fields
    - (c) TODO tickets added for real-cluster/GPU work
    - (d) pytest -q green

- ID: MK-054
  Title: Real-cluster e2e apply (CPU/GPU) for closed-loop --apply
  Status: DONE
  Acceptance criteria:
    - (a) real cluster verify/apply succeeds with `mk closed-loop run --apply`
    - (b) reports/artifacts recorded and match CLI_CONTRACTS
    - (c) pytest -q green

- ID: MK-055

  - MK-055 Evidence (real cluster RBAC patch deny)
    - KUBECONFIG: ~/.kube/mk055-no-patch.kubeconfig (SA mk055-rbac-deny/mk055-no-patch)
    - Plan: docs/evidence/mk055/k8s_plan.json (Deployment mk055-rbac-deny/mk055-demo)
    - Verify: docs/evidence/mk055/k8s_verify_latest.json
      - verify_blocker.kind = rbac_denied (Forbidden: cannot patch deployments.apps mk055-demo)
      - diagnostics.auth_can_i_get_deployments_by_namespace = {mk055-rbac-deny: true}
      - diagnostics.auth_can_i_patch_deployments_by_namespace = {mk055-rbac-deny: false}
    - kubectl auth can-i (under SA): get deployments.apps = yes; patch deployments.apps = no
  Title: Real-cluster RBAC failure diagnostics
  Status: DONE
  Acceptance criteria:
    - (a) `kubectl auth can-i` failures reflected in verify diagnostics
    - (b) `verify_blocker` matches live RBAC failures
    - (c) docs updated and pytest -q green

- ID: MK-056
  Title: Real-cluster namespace/deployment missing scenarios
  Status: DONE
  Acceptance criteria:
    - (a) verify reports show correct blockers for missing namespace/deployment
    - (b) tests capture real-cluster failure behavior
    - (c) pytest -q green

  Evidence (2026-02-11):
    - deployment_missing: report/mk056_verify_missing_deploy/k8s_verify_latest.json
    - namespace_missing: report/mk056_verify_missing_ns/k8s_verify_latest.json

- ID: MK-057
  Title: GPU telemetry ingestion from k8s observe
  Status: DONE
  Acceptance criteria:
    - (a) `mk observe --source k8s` ingests real GPU telemetry
    - (b) closed-loop proposals respond to GPU signals
    - (c) docs updated and pytest -q green

- ID: MK-058
  Title: Long-running closed-loop watch performance
  Status: DONE
  Acceptance criteria:
    - (a) watch runs N iterations with stable memory/CPU
    - (b) large JSONL streams do not regress throughput
    - (c) pytest -q green

- ID: MK-059
  Title: Multi-namespace mixed-plan verify behavior on real cluster
  Status: DONE
  Acceptance criteria:
    - (a) mixed namespaces avoid false RBAC checks
    - (b) verify diagnostics reflect per-item outcomes
    - (c) docs updated and pytest -q green

- ID: MK-060
  Title: Real incident playbooks (record/replay on real cluster)
  Status: DONE
  Acceptance criteria:
    - (a) at least one real incident playbook documented
    - (b) record/replay artifacts captured and reproducible
    - (c) docs updated and pytest -q green
  Evidence (2026-02-13):
    - docs/RECORD_REPLAY.md (Real incident playbook: RBAC patch denied)
    - docs/evidence/mk055/k8s_plan.json
    - docs/evidence/mk055/k8s_verify_latest.json
    - docs/evidence/mk060/rbac_replay/README.md
    - docs/evidence/mk060/rbac_replay/setup.sh
    - docs/evidence/mk060/rbac_replay/cleanup.sh

- ID: MK-061
  Title: Observe-only: оценка “упущенной выгоды” (hours/tokens/USD) без apply
  Status: DONE
  Acceptance criteria:
    - (a) summary/report содержит opportunity_hours_est / opportunity_usd_est / opportunity_tokens_est (или эквивалент)
    - (b) рядом зафиксированы метод/допущения (cost model: $/gpu-hour, $/cpu-hour, tokens/sec или tokens/step и т.п.)
    - (c) работает в observe-only (без MODEKEEPER_PAID), без изменения кластера
    - (d) docs обновлены и pytest -q green
  Evidence (2026-02-13):
    - docs/evidence/mk061/replay_run/closed_loop_latest.json
    - docs/evidence/mk061/replay_run/summary.md

- ID: MK-068
  Title: E2E demo сценарий: показать переходы режимов и отсутствие дерготни
  Status: DONE
  Owner: oleg
  DoD:
    - Один воспроизводимый прогон, который показывает: NORMAL→(DRIFT/BURST/STRAGGLER)→RECOVER→NORMAL.
    - Артефакты отчёта содержат mode/chord/blocked_reason/changed_knobs.
    - Демонстрация остаётся safe: plan-only/verify по умолчанию.
  Evidence (2026-02-13):
    - src/modekeeper/demo/mk068_demo.py
    - src/modekeeper/cli.py
    - src/modekeeper/demo/runner.py
    - tests/test_demo_mk068.py
    - tests/test_mk068_demo.py

- ID: MK-069
  Title: Passports v0 (после аккордов): схема + каталог шаблонов + onboarding
  Status: DONE
  Owner: oleg
  DoD:
    - Определить поля паспорта: allowed chords, allowed actuators hot/cold, limits, invariants, cooldowns, gates.
    - Каталог шаблонов под сегменты (pilot/safe/perf/cost/io/comm/recovery) как стартовые пресеты.
    - Зафиксировать правило: паспорта внедряем после Chords v1 (FSM/rollback).
  Evidence (2026-02-13):
    - docs/PASSPORTS.md
    - src/modekeeper/passports/v0.py
    - src/modekeeper/passports/templates/pilot.json
    - src/modekeeper/passports/templates/safe.json
    - src/modekeeper/passports/templates/perf.json
    - src/modekeeper/passports/templates/cost.json
    - src/modekeeper/passports/templates/io.json
    - src/modekeeper/passports/templates/comm.json
    - src/modekeeper/passports/templates/recovery.json
    - tests/test_passports_v0.py

- ID: MK-062
  Title: Chords v1 library (safe chord IDs + убрать timeout_ms из safe)
  Status: DONE
  Owner: oleg
  DoD:
    - Зафиксировать safe chord IDs v1 (минимум): NORMAL-HOLD, DRIFT-RETUNE, BURST-ABSORB, INPUT-STRAGGLER, RECOVER-RELOCK.
    - Убрать timeout_ms из safe-аккордов (если где-то фигурирует как safe-настройка).
    - pytest -q green.
    - Примечание: архивная реализация есть в теге archive/mk062-safe-chords-v1 (не слита в main).

  Evidence (2026-02-12):
    - src/modekeeper/chords/v1.py (SAFE_CHORD_IDS_V1)
    - src/modekeeper/policy/rules.py (timeout_ms tagged TIMEOUT-GUARD; safe chords use v1 IDs)
    - tests/test_mk062_chords_v1.py

- ID: MK-070
  Title: Scalar baseline policy (0..1 action) для честного сравнения
  Status: DONE
  Owner: oleg
  DoD:
    - Добавить baseline policy, выдающую 0..1 action (минимально) для сравнения с chord-policy.
    - Обеспечить детерминированность на replay (golden traces/фиксированный выбор).
    - Добавить тест(ы) сравнения поведения (pytest -q green).
  Evidence (2026-02-13):
    - src/modekeeper/policy/scalar.py
    - src/modekeeper/policy/rules.py
    - src/modekeeper/cli.py
    - tests/test_policy_scalar_baseline.py
    - tests/test_cli_policy_scalar.py

- ID: MK-071
  Title: Free Observation Passport observe_max (best-effort coverage + recommendation + propose-only + redaction)
  Status: DONE
  Owner: oleg
  DoD:
    - Ввести observe_max паспорт для бесплатного режима (best-effort coverage, без apply).
    - Report должен включать recommendation/proposals (propose-only), с редактированием чувствительных полей (redaction).
    - Тесты на отсутствие apply и наличие рекомендаций/редакции (pytest -q green).
  Evidence (2026-02-13):
    - src/modekeeper/passports/observe_max.py
    - src/modekeeper/cli.py
    - tests/test_passport_observe_max.py

- ID: MK-072
  Title: Docs: Custom Passports (Paid) — calibration workflow + intake + report template
  Status: DONE
  Owner: oleg
  DoD:
    - Описать workflow калибровки/интейка для платных паспортов (custom).
    - Добавить шаблон отчёта (report template) и минимальные требования к данным.
    - Проверить согласованность с текущими CLI_CONTRACTS/SNAPSHOT (pytest -q green).
  Evidence (2026-02-13):
    - docs/CUSTOM_PASSPORTS.md
    - docs/PASSPORTS.md
    - docs/SNAPSHOT.md
    - docs/CLI_CONTRACTS.md

- ID: MK-073
  Title: ROI: cost model + value_summary
  Status: DONE
  Owner: oleg
  DoD:
    - Определить cost model (что считаем: GPU-hours/throughput/latency и т.п.).
    - Добавить value_summary в отчёты (без ломки существующего контракта).
    - Тесты/инварианты на наличие полей (pytest -q green).
  Evidence (2026-02-13):
    - src/modekeeper/core/cost_model.py
    - src/modekeeper/core/value_summary.py
    - src/modekeeper/cli.py
    - tests/test_value_summary.py
    - tests/test_cli_value_summary.py

- ID: MK-074
  Title: ROI: Before/After report (chord vs scalar)
  Status: DONE
  Owner: oleg
  DoD:
    - Сгенерировать before/after сравнение chord-policy vs scalar baseline на одном и том же replay.
    - Итоговый отчёт должен быть воспроизводимым (deterministic).
    - Тест на формирование before/after артефактов (pytest -q green).
  Evidence (2026-02-13):
    - src/modekeeper/roi/mk074_before_after.py
    - src/modekeeper/roi/__init__.py
    - src/modekeeper/cli.py
    - tests/test_mk074_before_after.py

- ID: MK-075
  Title: Audit: decision trace + JSONL export
  Status: DONE
  Owner: oleg
  DoD:
    - Полный decision trace: mode/signals/chord/actions/results на каждый тик.
    - Экспорт в JSONL (машиночитаемо) и привязка к report artifacts.
    - Тесты на наличие/формат событий (pytest -q green).

  Evidence (2026-02-12):
    - src/modekeeper/audit/decision_trace.py (decision_trace_event.v0 JSONL writer)
    - closed_loop_latest.json links audit_trace.path=decision_trace_latest.jsonl
    - tests/test_mk075_decision_trace.py

- ID: MK-076
  Title: Governance: apply approval gate для cold/advanced
  Status: DONE
  Owner: oleg
  DoD:
    - Ввести approval gate для cold/advanced действий (явное разрешение).
    - По умолчанию: блокировка с explain reason (машиночитаемо).
    - Тесты на блок/разрешение (pytest -q green).

  Evidence (2026-02-12):
    - src/modekeeper/governance/approval.py (requires_approval, advanced sets)
    - src/modekeeper/safety/guards.py (split_actions_by_approval, reason=approval_required)
    - src/modekeeper/cli.py (--approve-advanced wired into run/watch)
    - tests/test_mk076_approval_gate.py

- ID: MK-077
  Title: Fleet (later): multi-cluster inventory view (skeleton)
  Status: DONE
  Owner: oleg
  DoD:
    - Скелет: сбор инвентаря кластеров/неймспейсов/деплойментов (без apply).
    - Артефакт inventory_latest.json + минимальный формат.
    - Тест на формат/детерминизм (pytest -q green).

  Evidence (2026-02-12):
    - src/modekeeper/fleet/inventory.py (collect_inventory, inventory.v0)
    - src/modekeeper/cli.py (mk fleet inventory)
    - tests/test_mk077_inventory.py

- ID: MK-078
  Title: Fleet (later): policy propagation + versioning + rollback (skeleton)
  Status: DONE
  Owner: oleg
  DoD:
    - Скелет: versioning policy bundles + rollback до предыдущей версии.
    - Безопасно по умолчанию: propose/plan-only.
    - Тесты на формат/rollback path (pytest -q green).

  Evidence (2026-02-12):
    - src/modekeeper/fleet/policy_propagation.py (versioning + rollback fields, policy_propagation.v0)
    - src/modekeeper/cli.py (mk fleet policy, policy_propagation_latest.json)
    - tests/test_mk078_policy_propagation.py

- ID: MK-079
  Title: Telemetry: file observe parses worker_latencies_ms
  Status: DONE
  Owner: oleg
  DoD:
    - FileSource читает worker_latencies_ms из JSONL/CSV (JSON array string).
    - Backward compatible: при отсутствии/невалидности worker_latencies_ms fallback=[latency_ms].
    - Тест: straggler сигнал поднимается и появляется timeout_ms action (pytest -q green).

  Evidence (2026-02-12):
    - src/modekeeper/telemetry/file_source.py (_parse_worker_latencies + wiring)
    - tests/test_file_source_worker_latencies.py

- ID: MK-080
  Title: Free ROI estimate command (non-actionable)
  Status: DONE
  Owner: oleg
  DoD:
    - Добавить `mk roi estimate` для бесплатной, не-действенной ROI-оценки.
    - Артефакт содержит только summary/potential/notes, без actions/knobs/chords/plan/trace.
    - Детерминированный JSON output (sort_keys + стабильные списки).
    - Тест покрытия сценария bursty incident (pytest -q green).

  Evidence (2026-02-12):
    - src/modekeeper/roi/estimate.py
    - src/modekeeper/cli.py
    - tests/test_mk080_roi_estimate.py

- ID: MK-081
  Title: Public free observe_max report-only command
  Status: DONE
  Owner: oleg
  DoD:
    - Добавить `mk passport observe-max-report` с теми же observe аргументами, что и `observe-max`, и обязательным `--out`.
    - Команда пишет только `observe_max_latest.json` и не создаёт `passport_observe_max_latest.json`.
    - Выход остаётся детерминированным и redacted (без action/chord/plan/trace деталей).
    - Тест покрытия на report-only поведение (pytest -q green).

  Evidence (2026-02-12):
    - src/modekeeper/cli.py
    - tests/test_passport_observe_max_report_only.py
    - pytest -q tests/test_passport_observe_max.py tests/test_passport_observe_max_redaction.py tests/test_passport_observe_max_report_only.py

- ID: MK-082
  Title: Licensing v1: signed offline license + entitlement gates (no product bypass)
  Status: DONE
  Owner: oleg
  DoD:
    - Добавить модуль лицензии (подпись + оффлайн verify):
      - Формат license.v1 (JSON): {schema_version, org, issued_at, expires_at, entitlements[], bindings?, signature}.
      - Подпись ed25519 по canonical payload (без signature).
      - В репо хранится public key (или allowlist ключей) для verify.
    - CLI:
      - `mk license verify --license <path>`:
        - exit 0 если license_ok=true, иначе exit 2
        - артефакт: `license_verify_latest.json` (schema: license_verify.v0) с {license_ok, reason, expires_at, entitlements_summary}
    - Интеграция гейтов:
      - `apply` и любые paid/advanced ветки опираются на `license_ok`, а не на `MODEKEEPER_PAID`.
      - `MODEKEEPER_PAID` допускается ТОЛЬКО как internal/CI override (моки), не как продуктовая фича; в прод-логике должен быть выключен/запрещён.
      - Все block_reason должны быть детерминированы: license_missing / license_invalid / license_expired / entitlement_missing / binding_mismatch.
    - Тесты (pytest -q green):
      - валидная лицензия (ok)
      - поддельная подпись (blocked)
      - expired (blocked)
      - entitlement_missing (blocked)
      - binding_mismatch (blocked)

- ID: MK-083
  Title: Policy bundle v1: versioning + provenance + rollback plumbing
  Status: DONE
  Owner: oleg
  DoD:
    - Добавлен контракт `policy_bundle.v1` с детерминированной сериализацией (`sort_keys`).
    - Bundle создаётся в полезных путях:
      - `mk closed-loop run` -> `policy_bundle_latest.json`
      - `mk k8s apply` -> `policy_bundle_latest.json`
    - Provenance включает `git_commit`, `git_dirty`, `host`.
    - Rollback plumbing (skeleton):
      - если verify-отчёт найден в `--out`, пишется `rollback_plan_latest.json` (детерминированный скелет),
      - в bundle заполняются `rollback.from_verify_report` и `rollback.rollback_plan_path`.
    - Добавлены тесты на emission и базовый контракт bundle/rollback.

- ID: MK-084
  Title: Chord catalog v1 + safety envelope contract (moat foundation)
  Status: DONE
  Owner: oleg
  DoD:
    - Ввести `chord_catalog.v1` (JSON) как контракт:
      - chords[].{id, intent, risk_tier, required_signals[], invariants[], knobs_touched[], cooldown_ms?, budget?}
      - В каталоге НЕТ конкретных target-значений (только “что трогает”).
    - Валидатор каталога:
      - `mk chords validate --catalog <path>` (exit 0/2)
      - артефакт: `chords_validate_latest.json` (schema: chords_validate.v0)
    - Интеграция с guardrails:
      - Любая генерация action/chord должна быть проверяема через envelope:
        - chord id ∈ catalog
        - risk_tier корректно гейтится (approval_required и т.п.)
        - cooldown/budget учитываются (пока можно как skeleton: хранить, но не enforce полностью)
    - Документация:
      - описать “Chord = macro-op с инвариантами” и как добавлять новый chord через catalog.
    - Тесты (pytest -q green):
      - каталог валидируется
      - неизвестный chord блокируется guardrails
      - известный chord проходит (с корректным tier/approval)

- ID: MK-085
  Title: Kill-switch is absolute (blocks apply even under internal override)
  Status: DONE
  Owner: oleg
  DoD:
    - Сделать kill-switch абсолютным:
      - `MODEKEEPER_KILL_SWITCH=1` блокирует любой apply (k8s apply, closed-loop --apply) всегда.
      - `MODEKEEPER_INTERNAL_OVERRIDE=1` НЕ обходит kill-switch.
    - Контракт блокировки:
      - block_reason/ apply_blocked_reason должен стать `kill_switch_active` (детерминированно).
      - При kill-switch не должно быть попытки kubectl patch.
    - Тесты (pytest -q green):
      - сценарий internal override + kill-switch => blocked (`kill_switch_active`)
      - обновить существующие тесты, которые сейчас ожидают обратное поведение.
    - Документация: кратко зафиксировать приоритет kill-switch над всем.
  Evidence (2026-02-19):
    - tests/test_mk085_killswitch_absolute.py
    - tests/test_cli_artifacts.py
    - tests/test_mk082_license_gates.py
    - artifacts: `closed_loop_latest.json` + `decision_trace_latest.jsonl` + `explain.jsonl` include
      `kill_switch_active=true`, `apply_blocked_reason=kill_switch_active`, `kill_switch_signal=env:MODEKEEPER_KILL_SWITCH`

- ID: MK-086
  Title: Licensing key management v1.1: multi-key rotation + kid (optional trust chain)
  Status: DONE
  Owner: oleg
  DoD:
    - Поддержать несколько публичных ключей и ротацию:
      - keyring allowlist: JSON map `{kid -> pubkey_b64_raw32}`
      - в license payload добавить `kid` (string) и включать его в подписываемый payload
      - verify выбирает ключ по kid (если kid задан), иначе (fallback) может перебрать allowlist
    - Поведение ошибок:
      - неизвестный kid => license_invalid
      - подпись не сходится => license_invalid
    - (Опционально) задел под цепочку доверия:
      - root keyring -> issuer keys (минимальный скелет структуры, без обязательного enforcement если рано)
    - Тесты (pytest -q green):
      - ok: kid известен, подпись валидна
      - blocked: kid неизвестен
      - ok: ротация — 2 ключа, проверка по правильному kid
    - Документация: как делать ротацию и почему нужен kid.
  Evidence (2026-02-19):
    - tests/test_mk082_license_verify.py
    - tests/test_mk086_license_kid_and_rotation.py
    - src/modekeeper/license/verify.py
    - docs/INTERNAL_LICENSE_ISSUANCE.md
    - artifact contract: `license_verify_latest.json` includes
      `license_ok`, `kid`, `issuer`, `expiry`, `entitlements`, `reason_code`, `failure_code`, `failure_detail`

- ID: MK-110
  Title: Optional trust-chain verification mode (root -> issuer signed keyset)
  Status: TODO
  Owner: oleg
  DoD:
    - Реализовать конфигурируемый режим chain verification (по умолчанию off; allowlist-by-kid остаётся default).
    - Root key проверяет signed issuer keyset; issuer key проверяет license signature.
    - Bad issuer keyset signature детерминированно блокирует verify.
    - Тесты:
      - bad keyset signature -> block
      - valid keyset signature + valid license -> pass
    - Документация: migration/rotation workflow для chain mode.

- ID: MK-087
  Title: Trainer v1: replace pause image with minimal knob-aware container + stdout visibility
  Status: DONE
  Owner: oleg
  DoD:
    - Заменить образ деплоя `trainer` (kind smoke) с `pause` на наш минимальный контейнер `modekeeper-trainer`.
    - Контейнер должен:
      - читать pod annotations через Downward API файл (например, `/etc/podinfo/annotations`)
      - извлекать все ключи с префиксом `modekeeper/knob.`
      - печатать в stdout текущее состояние knob’ов (одна строка на knob) + периодический heartbeat.
      - работать в sleep-loop (не завершаться).
    - Манифест/чарт `trainer` должен монтировать Downward API annotations файл внутрь контейнера.
    - Kind smoke:
      - `mk ... --apply` меняет `modekeeper/knob.*` на деплое/pod
      - `kubectl logs deploy/trainer` отражает новые значения без рестарта (в разумный интервал, до 30s).
    - Тесты:
      - unit-тест парсинга annotations → knobs map (детерминированно).
  Evidence (2026-02-13):
    - src/modekeeper/trainer/__main__.py
    - src/modekeeper/trainer/knobs.py
    - docker/trainer/Dockerfile
    - k8s/trainer-minimal.yaml (DownwardAPI annotations -> /etc/podinfo/annotations)
    - scripts/kind-bootstrap.sh (docker build + kind load)
    - tests/test_trainer_knobs_parse.py
    - Commit: 762c417
    - Kind smoke: scripts/kind-bootstrap.sh
    - Live knob update (no restart): kubectl annotate pod ... modekeeper/knob.concurrency=5 ; logs show step_time_ms=1000
    - Live knob update (no restart): kubectl annotate pod ... modekeeper/knob.dataloader_prefetch_factor=5 ; logs show step_time_ms=500
    - commit: `e4f720b` (trainer: emit knob annotations from downward API in loop)
    - verification: `pytest -q tests/test_trainer_main.py tests/test_trainer_knobs_parse.py` (green)

- ID: MK-088
  Title: Real-cluster e2e apply + RBAC deny diagnostics
  Status: DONE
  Owner: oleg
  DoD:
    - Добавить диагностику RBAC deny в verify/apply:
      - фиксировать `verb`, `resource`, `apiGroup`, `namespace`, `name` (если доступно)
      - reason должен быть детерминированный (например `rbac_deny` + уточнение)
      - в отчёте/summary давать actionable hint (какое правило RBAC нужно).
    - E2E на живом кластере:
      - verify проходит при корректных правах
      - apply проходит при корректных правах (минимально необходимых).
    - Тесты:
      - unit/contract: рендер deny-диагностики в отчёт (snapshot/field asserts).
  Evidence (2026-02-13):
    - src/modekeeper/k8s/rbac_diagnostics.py (parse_k8s_forbidden)
    - src/modekeeper/k8s/__init__.py
    - src/modekeeper/cli.py (details.rbac wiring + verify_rbac_hint)
    - tests/test_rbac_diagnostics_parse.py
    - tests/test_k8s_verify.py (rbac_denied -> details.rbac asserts)
    - Commit: b15d616
    - pytest -q tests/test_rbac_diagnostics_parse.py
    - pytest -q

- ID: MK-089
  Title: GPU telemetry ingest + long-running closed-loop watch reliability
  Status: DONE
  Owner: oleg
  DoD:
    - Добавить сбор GPU телеметрии (минимальный набор) в observe/closed-loop:
      - метрики/значения попадают в артефакты с timestamp.
    - Надёжность `mk closed-loop watch`:
      - длительный прогон (>= 1 час) без роста памяти и без деградации скорости цикла.
      - корректный shutdown (SIGINT/SIGTERM) с финальным summary/artifacts.
    - Тесты:
      - unit/contract на формат/наличие telemetry полей.
  Evidence (2026-02-13):
    - src/modekeeper/telemetry/file_source.py (GPU fields for file source + gpu_mem_util_pct derivation)
    - src/modekeeper/cli.py (telemetry payload in observe/closed-loop reports; watch loop graceful shutdown and final artifact flush)
    - tests/test_mk089_telemetry_and_watch.py
    - pytest -q tests/test_mk089_telemetry_and_watch.py
    - pytest -q

- ID: MK-090
  Title: Multi-namespace mixed plans + incident playbooks
  Status: DONE
  Owner: oleg
  DoD:
    - План/verify/apply поддерживает несколько namespace/deployment в одном запуске:
      - результаты группируются и отчёты сохраняют полную разметку объектов.
    - Добавить playbooks в docs:
      - kill-switch
      - license expired/invalid
      - rbac deny
      - rollback workflow (как пользоваться rollback_plan_latest.json).
    - Тесты:
      - contract: multi-object report shape (минимально).
  Evidence (2026-02-13):
    - src/modekeeper/cli.py (multi-object plan parsing for verify/apply, fail-fast iteration, report objects/object identity)
    - tests/test_k8s_multi_object_plan.py
    - docs/PLAYBOOKS.md
    - docs/WORKFLOW.md (link to playbooks)
    - docs/SNAPSHOT.md
    - pytest -q tests/test_k8s_multi_object_plan.py
    - pytest -q
    - Commit: 5b3f1da

- ID: MK-091
  Title: Environment fingerprint + heterogeneity signal (safe-by-default)
  Status: DONE
  Owner: oleg
  DoD:
    - Добавить `report.environment` в observe/closed-loop артефакты:
      - `nodes_seen[]`, `gpu_models_seen[]`, `unstable`, `notes[]`
      - `unstable=true`, если в выборке >1 node или >1 gpu model.
    - Расширить telemetry points optional полями:
      - `node`, `gpu_model` (если присутствуют в sample).
      - `ts_ms` обязателен для каждой точки.
    - File source:
      - парсинг `node`/`node_name`, `gpu_model`/`gpu_name` из JSONL/CSV.
    - K8s log source (best-effort):
      - аннотация samples `node` через `nodeName` выбранного pod.
    - Тесты:
      - новый observe/file mixed env тест на `environment.unstable==true`;
      - ассерты `telemetry.points` (`ts_ms` always, `node/gpu_model` optional).
    - Документация:
      - короткая секция про heterogeneous clusters и pinning (`nodeSelector`/`affinity`).
    - pytest -q green.
  Evidence (2026-02-13):
    - src/modekeeper/telemetry/models.py
    - src/modekeeper/telemetry/file_source.py
    - src/modekeeper/telemetry/k8s_log_source.py
    - src/modekeeper/cli.py
    - tests/test_mk091_environment_fingerprint.py
    - docs/WORKFLOW.md

- ID: MK-092
  Title: Customer quickstart + reproducible evidence (safe mode)
  Status: DONE
  Owner: oleg
  DoD:
    - Добавить customer-facing quickstart:
      - безопасный запуск (verify/observe/closed-loop dry-run/watch)
      - heterogeneous clusters: ModeKeeper работает, но сигналит `environment.unstable=true`
    - Добавить reproducible evidence без k8s (file source):
      - observe/closed-loop/watch артефакты в `docs/evidence/mk092_quickstart/`
    - README содержит ссылку на quickstart.
  Evidence (2026-02-14):
    - docs/QUICKSTART.md
    - docs/evidence/mk092_quickstart/README.md
    - docs/evidence/mk092_quickstart/observe_mixed_env.jsonl
    - docs/evidence/mk092_quickstart/out_observe/observe_latest.json
    - docs/evidence/mk092_quickstart/out_closed_loop/closed_loop_latest.json
    - docs/evidence/mk092_quickstart/out_closed_loop/summary.md
    - docs/evidence/mk092_quickstart/out_closed_loop/k8s_plan.json
    - docs/evidence/mk092_quickstart/out_closed_loop/k8s_plan.kubectl.sh
    - docs/evidence/mk092_quickstart/out_closed_loop/policy_bundle_latest.json
    - docs/evidence/mk092_quickstart/out_watch/watch_latest.json
    - docs/evidence/mk092_quickstart/out_watch/watch_summary.md

- ID: MK-093
  Title: Customer eval one-liner (safe-by-default)
  Status: DONE
  Owner: oleg
  DoD:
    - Добавить `mk eval` с подкомандами `file` и `k8s`.
    - Safe-by-default: read-only, без apply/записей в кластер.
    - Артефакты в `--out`:
      - `eval_latest.json` (schema `eval.v0`)
      - `eval_summary.md`
    - Executive summary печатается в stdout.
    - Детерминизм:
      - `json.dumps(..., sort_keys=True)` для eval JSON;
      - стабильный порядок list-полей.
    - Тест:
      - `eval file` на `docs/evidence/mk092_quickstart/observe_mixed_env.jsonl` с ассертами output fields.
  Evidence (2026-02-14):
    - src/modekeeper/cli.py
    - tests/test_mk093_customer_eval.py
    - docs/QUICKSTART.md
    - docs/TICKETS.md
    - docs/SNAPSHOT.md

- ID: MK-094
  Title: Add customer-safe k8s preflight command
  Status: DONE
  Owner: oleg
  DoD:
    - Добавить `mk k8s preflight` (read-only) под группой `k8s`.
    - Defaults: `--k8s-namespace default`, `--k8s-deployment trainer`, `--out report/preflight`.
    - Выполнить best-effort preflight checks через kubectl и писать:
      - `preflight_latest.json` (schema `preflight.v0`, deterministic/sort_keys)
      - `preflight_summary.md`
      - `explain.jsonl`
    - stdout executive summary:
      - `ok=... top_blocker=... context=... ns=... deploy=... preflight=... summary=...`
    - Минимальный unit test с mocked kubectl runner (без реального k8s).
  Evidence (2026-02-14):
    - src/modekeeper/cli.py
    - tests/test_k8s_preflight.py
    - docs/QUICKSTART.md
    - docs/TICKETS.md
    - docs/SNAPSHOT.md

- ID: MK-095
  Title: Make GPU/workload visibility explicit (customer-safe) + small UX fixes
  Status: DONE
  Owner: oleg
  DoD:
    - `mk k8s preflight`:
      - `preflight_latest.json` дополнен полями:
        - `gpu_capacity_present` (bool)
        - `nvidia_device_plugin_present` (bool, best-effort)
        - `deploy_gpu_request` (int sum request/limit `nvidia.com/gpu`)
        - `notes` (warnings-only)
      - missing GPU/plugin/deploy GPU request не ставят `top_blocker` (только `notes`)
      - `preflight_summary.md` и stdout summary расширены этими полями.
    - `mk eval k8s`:
      - `sample_count` добавлен в stdout summary и `eval_summary.md`
      - `eval_latest.json` содержит `telemetry_points_included=false` (явно).
    - `closed_loop_latest.json`:
      - `proposed_actions_count` всегда int (0 when none).
    - docs обновлены.
    - минимальные focused tests обновлены.
  Evidence (2026-02-14):
    - src/modekeeper/cli.py
    - tests/test_k8s_preflight.py
    - tests/test_mk093_customer_eval.py
    - docs/QUICKSTART.md
    - docs/TICKETS.md
    - docs/SNAPSHOT.md

- ID: MK-096
  Title: Investor-grade ROI/value report (customer-safe, read-only)
  Status: DONE
  Owner: oleg
  DoD:
    - Добавить `mk roi report` под группой `roi`:
      - `--preflight` default `report/preflight/preflight_latest.json`
      - `--eval` default `report/eval_k8s/eval_latest.json`
      - `--watch` default `report/watch_k8s/watch_latest.json`
      - `--out` default `report/roi`
    - Best-effort ingest 3 входов; при missing/invalid JSON:
      - `ok=false`, `top_blocker` выставлен,
      - всё равно пишутся `roi_latest.json`, `roi_summary.md`, `explain.jsonl`.
    - `roi_latest.json` (schema `roi.v0`) содержит executive snapshot:
      - environment fingerprint (prefer `eval.environment`),
      - preflight visibility subset,
      - watch summary subset,
      - `opportunity_hours_est`/`proposed_actions_count` из последнего iteration report (если доступно),
      - deterministic list ordering + `json.dumps(..., sort_keys=True)`.
    - `roi_summary.md` (RU, concise) содержит:
      - started/finished/duration, ok/top_blocker,
      - environment/preflight/watch key lines,
      - `opportunity_hours_est`,
      - блок "Что делать дальше".
    - stdout one-line executive summary:
      - `roi_ok=... top_blocker=... opportunity_hours_est=... roi=... summary=...`
    - Один focused unit test для ROI report.
  Evidence (2026-02-14):
    - src/modekeeper/cli.py
    - tests/test_mk096_roi_report.py
    - docs/QUICKSTART.md
    - docs/TICKETS.md
    - docs/SNAPSHOT.md

- ID: MK-097
  Title: SaaS seams: exportable bundle + manifest (offline-first, customer-safe)
  Status: DONE
  Owner: oleg
  DoD:
    - Добавить `mk export bundle --in <report_dir> --out <dir>` (defaults: `report` -> `report/bundle`).
    - Best-effort скан известных latest-артефактов + summary/explain.
    - Писать `bundle_manifest.json` (schema `bundle.v0`) и `bundle.tar.gz` детерминированно.
    - Писать `bundle_summary.md` (RU, concise) + one-line stdout summary.
    - Missing inputs не роняют команду: фиксируются в `notes`, формируется частичный bundle.
    - Один focused unit test на manifest/files ordering/sha/tar/summary/stdout.
  Evidence (2026-02-14):
    - src/modekeeper/cli.py
    - tests/test_mk097_export_bundle.py
    - docs/SAAS_SEAMS.md
    - docs/QUICKSTART.md
    - docs/TICKETS.md
    - docs/SNAPSHOT.md

- ID: MK-098
  Title: Demo trainer emits loss/throughput for CPU clusters (ROI no longer blocked by loss_missing)
  Status: DONE
  Owner: oleg
  DoD:
    - Добавить demo trainer workload для `deploy=trainer` в существующем k8s паттерне.
    - Логи trainer в стабильном machine-parseable JSONL формате:
      - `ts`, `step`, `loss`, `throughput` (continuous).
    - `mk eval k8s` (observe-source k8s):
      - если pod/deployment аннотирован `modekeeper/telemetry=stdout-jsonl`,
      - читать `kubectl logs --since ...`,
      - парсить JSONL loss/throughput в telemetry samples.
    - Backward compatibility:
      - без аннотации сохраняется старый parser/поведение.
    - `eval_latest.json`:
      - `telemetry_points_included=true`, когда в выборке есть loss+throughput.
      - `signals.notes` не содержит `loss_missing` при валидной telemetry.
    - Один focused unit test на JSONL ingest + отсутствие `loss_missing`.
  Evidence (2026-02-14):
    - src/modekeeper/trainer/__main__.py
    - k8s/trainer-demo-cpu.yaml
    - src/modekeeper/telemetry/k8s_log_source.py
    - src/modekeeper/telemetry/models.py
    - src/modekeeper/cli.py
    - tests/test_mk098_stdout_jsonl_ingest.py
    - docs/QUICKSTART.md
    - docs/TICKETS.md
    - docs/SNAPSHOT.md
- ID: MK-114
  Title: Release automation (PyPI Trusted Publishing/OIDC) + packaging policy guard (public = safe agent only)
  Status: DONE
  DoD:
    - Add CI release pipeline that publishes to PyPI via Trusted Publishing (OIDC), without API tokens.
    - Release triggers on annotated tag `vX.Y.Z` and verifies tag ↔ package version match.
    - Pipeline runs: build → twine check → install-from-dist smoke → publish.
    - Add packaging policy guard in CI: fail release if forbidden/proprietary-only artifacts would be shipped in public PyPI dist.
    - Add smoke test from built wheel in a clean venv:
      - `mk --help`
      - `mk doctor`
      - `mk quickstart --out ...` and verify `plan/decision_trace_latest.jsonl` exists.
  Acceptance criteria:
    - A maintainer can create tag `vX.Y.Z` and CI publishes the matching version to PyPI automatically.
    - No long-lived PyPI tokens are required/stored for publishing (OIDC only).
    - Public PyPI artifacts policy is enforced automatically on every release (guard is mandatory and blocks publish on violation).
    - Release pipeline produces auditable logs and preserves build artifacts as CI artifacts.
  Evidence (2026-02-16):
    - .github/workflows/release-pypi.yml (Trusted Publishing via OIDC)
    - bin/mk-pypi-guard (public dist guard)
    - commit: 8e78208
    - local: build + twine check + guard + install-from-dist smoke (mk doctor/quickstart)
