# ModeKeeper Project Map

## What Exists Today
- CLI-first product (`mk`) with read-only default flow: `observe`, `eval`, `closed-loop run/watch` dry-run, `k8s render`, `k8s verify`.
- Paid, gated mutate path: `k8s apply` and `closed-loop ... --apply` blocked by kill-switch, license validity/entitlements, and `verify_ok=true`.
- Kubernetes plan pipeline: build plan, render kubectl script, verify context/object/dry-run checks, and apply with deterministic artifacts.
- Onboarding tooling for customers/operators: `bin/mk-install`, `mk --help`, and `docs/QUICKSTART.md`.
- License system with keyring + `kid` selection/rotation, offline path resolution, and clear block reasons.
- Safety + governance foundations: guardrails, approval split (hot/cold/advanced), explain logs, decision trace JSONL.
- Policy engines: chord policy (primary) and scalar baseline; policy bundle export and hashes.
- Telemetry ingestion from synthetic, file, and k8s logs; observe raw recorder; watch aggregation/reporting.
- Chords v1 + passports v0 templates/contracts, including observe-max free passport reporting.
- ROI/value reporting (`estimate`, before/after, value summary) and demo scripts for safety gates and drift/apply flows.

## Repo Map
- `src/modekeeper/`: Core product code and CLI implementation.
- `src/modekeeper/core/`: Mode/state machine, signal analysis, summaries, value/opportunity models.
- `src/modekeeper/telemetry/`: Synthetic/file/k8s sources, collector, raw recorder, telemetry schemas.
- `src/modekeeper/k8s/`: K8s helpers and RBAC diagnostics parsing.
- `src/modekeeper/license/`: License verification, canonicalization, public key allowlist.
- `src/modekeeper/safety/`: Guardrails, rollback/explain helpers.
- `src/modekeeper/policy/`: Chord/scalar policies, actions, policy bundle generation.
- `src/modekeeper/chords/`: Chord catalog and v1 chord logic.
- `src/modekeeper/passports/`: Passport schema/validation/templates and observe-max outputs.
- `src/modekeeper/roi/`: ROI estimation and before/after reporting.
- `src/modekeeper/demo/`: Demo orchestration used by CLI and shell scripts.
- `src/modekeeper/governance/`, `src/modekeeper/audit/`, `src/modekeeper/fleet/`: Approval, audit trace, and fleet scaffolding.
- `bin/`: Operator scripts (`mk-install`, `mk-doctor`, demos, dev license minting).
- `docs/`: Product, workflow, contracts, roadmap/tickets, and evidence.
- `tests/`: CLI, k8s pipeline, licenses, safety gates, telemetry, policy/chords/passports, ROI, demos.
- `k8s/`, `demo/`, `docker/`: Runtime manifests, demo assets, and container artifacts.
- `scripts/`: Local/kind/e2e helper scripts.

## Where To Look
| Feature/Topic | Primary files |
|---|---|
| CLI | `src/modekeeper/cli.py` |
| Installer | `bin/mk-install`, `tests/test_mk_install.py` |
| Licensing | `src/modekeeper/license/verify.py`, `src/modekeeper/license/public_keys.json`, `tests/test_mk082_license_gates.py`, `tests/test_mk086_license_kid_and_rotation.py` |
| K8s | `src/modekeeper/cli.py`, `src/modekeeper/adapters/kubernetes.py`, `src/modekeeper/k8s/rbac_diagnostics.py`, `tests/test_k8s_verify.py`, `tests/test_k8s_apply_real.py` |
| Telemetry | `src/modekeeper/telemetry/collector.py`, `src/modekeeper/telemetry/file_source.py`, `src/modekeeper/telemetry/k8s_log_source.py`, `tests/test_mk089_telemetry_and_watch.py` |
| Safety | `src/modekeeper/safety/guards.py`, `src/modekeeper/safety/explain.py`, `tests/test_safety_guardrails.py`, `tests/test_mk085_killswitch_absolute.py` |
| Policy | `src/modekeeper/policy/chords.py`, `src/modekeeper/policy/scalar.py`, `src/modekeeper/policy/bundle.py`, `tests/test_policy_scalar_baseline.py` |
| Passports | `src/modekeeper/passports/v0.py`, `src/modekeeper/passports/observe_max.py`, `src/modekeeper/passports/templates/`, `tests/test_passports_v0.py` |
| Chords | `src/modekeeper/chords/v1.py`, `src/modekeeper/chords/catalog.py`, `src/modekeeper/chords/catalog_v1.json`, `tests/test_mk062_chords_v1.py` |
| ROI | `src/modekeeper/roi/estimate.py`, `src/modekeeper/roi/mk074_before_after.py`, `tests/test_mk096_roi_report.py` |
| Demo | `bin/mk-demo-safety-gates`, `bin/mk-demo-k8s-drift`, `bin/mk-demo-sales`, `src/modekeeper/demo/mk068_demo.py`, `tests/test_mk068_demo.py` |
| Tests | `tests/` (start with `tests/test_cli_artifacts.py`, `tests/test_closed_loop_apply_pipeline.py`, `tests/test_cli_doctor.py`) |

## Golden Commands
- `./bin/mk-install`
- `mk --help`
- `mk observe --help`
- `mk eval file --path tests/data/observe/stable.jsonl --out report/_eval`
- `mk observe --source file --path tests/data/observe/realistic_dirty.jsonl --duration 2s --out report/_observe`
- `mk closed-loop run --scenario drift --dry-run --out report/_closed_loop`
- `mk k8s verify --plan report/_closed_loop/k8s_plan.json --out report/_verify`
- `pytest -q tests/test_mk_install.py`

## Next Planned Work
- `MK-112` (TODO): PyPI landing README + enterprise quickstart (install, eval, observe, closed-loop gating) from `docs/TICKETS.md`.
- Passport runtime enablement beyond current contracts/templates (SNAPSHOT notes passports are the next runtime stage).
- Advanced chord enablement only after required telemetry + explicit profile authorization (currently off-by-default per `docs/SNAPSHOT.md` and `docs/CHORDS.md`).
- Continue keeping `plan-only + verify` as the default operational posture while paid apply remains strictly gated (explicit product direction in `docs/SNAPSHOT.md`).
