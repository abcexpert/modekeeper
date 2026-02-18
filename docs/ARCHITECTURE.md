# ModeKeeper Architecture (as implemented)

## Scope and runtime model
ModeKeeper is a Python package with a single `argparse` CLI entrypoint: `mk` (`src/modekeeper/cli.py`).

The implemented runtime is verify-first and report-first:
- telemetry is ingested from synthetic/file/k8s sources;
- signals are analyzed;
- actions are proposed by policy engines;
- safety/governance gates produce plan/verify artifacts;
- outputs are persisted as JSON/JSONL/Markdown artifacts under `--out` (default usually `report/`).

The command surface is centered on read-only paths (`observe`, `eval`, `quickstart`, `k8s verify`, `k8s preflight`, `export bundle`). Apply/mutate entrypoints are hard-gated and still generate deterministic artifacts for traceability.

## Package map

### Entrypoint and orchestration
- `src/modekeeper/cli.py`
- Builds parser tree, wires all `cmd_*` handlers, resolves env defaults, and writes standard artifacts.

### Core decision engine
- `src/modekeeper/core/analysis.py`: converts telemetry samples into signals.
- `src/modekeeper/core/state_machine.py`, `src/modekeeper/core/modes.py`: mode state tracking.
- `src/modekeeper/core/summary.py`: human-readable decision/observe summaries.
- `src/modekeeper/core/opportunity.py`, `src/modekeeper/core/value_summary.py`, `src/modekeeper/core/cost_model.py`: opportunity/value estimation and cost model.

### Telemetry ingestion
- `src/modekeeper/telemetry/sources.py`: synthetic source.
- `src/modekeeper/telemetry/file_source.py`: file source (`jsonl/csv`) + ingest metadata.
- `src/modekeeper/telemetry/k8s_log_source.py`: k8s logs source using `kubectl`.
- `src/modekeeper/telemetry/collector.py`: collector abstraction returning normalized samples.
- `src/modekeeper/telemetry/raw_recorder.py`: raw line recording helpers.

### Policy and action proposal
- `src/modekeeper/policy/rules.py`: proposal entry (`propose_actions`).
- `src/modekeeper/policy/chords.py`, `src/modekeeper/policy/scalar.py`: policy variants.
- `src/modekeeper/policy/actions.py`: action model.
- `src/modekeeper/policy/bundle.py`: policy bundle artifact generation (`policy_bundle_latest.json`).

### Safety and governance
- `src/modekeeper/safety/guards.py`: guardrails and kill-switch checks.
- `src/modekeeper/governance/approval.py`: split actionable vs blocked actions.
- `src/modekeeper/safety/explain.py`: explain log writer.
- `src/modekeeper/audit/decision_trace.py`: append-only decision trace JSONL contract.

### Kubernetes adapters and diagnostics
- `src/modekeeper/adapters/kubernetes.py`: build k8s patch plan from proposed actions.
- `src/modekeeper/k8s/rbac_diagnostics.py`: parse forbidden/RBAC diagnostics.

### Domain modules
- `src/modekeeper/passports/*`: templates, schema validation, observe-max artifacts.
- `src/modekeeper/chords/*`: chord catalog and validation.
- `src/modekeeper/roi/*`: ROI estimates and reports.
- `src/modekeeper/fleet/*`: inventory/policy propagation collection.
- `src/modekeeper/license/*`: offline license verification and keyring loading.

## Main data flows

### 1) Observe flow (`mk observe`)
1. Parser resolves source/flags/duration.
2. `_collect_observe_samples` reads samples from synthetic/file/k8s.
3. `analyze_signals` computes drift/burst/straggler/gpu signals.
4. CLI writes report envelope and artifacts:
   - `explain.jsonl`
   - `report_<ts>.json`
   - `observe_latest.json`

No actions are proposed/applied in this flow.

### 2) Eval flow (`mk eval file|k8s`)
1. Same telemetry ingestion + signal analysis.
2. `propose_actions(policy=chord|scalar)` builds deterministic proposal list.
3. For k8s source, plan and verify are generated:
   - `k8s_plan.json`
   - `k8s_plan.kubectl.sh`
   - `k8s_verify_latest.json`
4. Eval artifacts:
   - `eval_latest.json`
   - `eval_summary.md`
   - `explain.jsonl`

### 3) Closed-loop run/watch (`mk closed-loop run|watch`)
1. Collect samples and compute signals.
2. Build proposed actions via policy.
3. Apply guardrails and approval splitting.
4. Build k8s patch plan (`build_k8s_plan`) and shell replay script.
5. Persist decision artifacts:
   - `closed_loop_latest.json`
   - `summary.md`
   - `decision_trace_latest.jsonl`
   - `policy_bundle_latest.json`
   - plus `k8s_plan.json` and `k8s_plan.kubectl.sh`
6. `watch` repeats this per `iter_XXXX/` and aggregates into:
   - `watch_latest.json`
   - `watch_summary.md`

### 4) Verify/apply path
- Verify (`mk k8s verify`) checks context, namespace/deployment existence, and `kubectl patch --dry-run=server` viability; writes `k8s_verify_latest.json` + explain events.
- Apply entrypoints (`mk k8s apply`, `mk closed-loop ... --apply`) are gated. In public flow they still emit canonical apply artifacts (`k8s_apply_latest.json`) with explicit block reason.

## Key abstractions and contracts
- `ModeStateMachine`: normalized mode context (`OBSERVE_ONLY`, `CLOSED_LOOP`, etc.).
- Telemetry source contract: any source consumed by `TelemetryCollector` must emit sample objects expected by analysis (`timestamp_ms`, `latency_ms`, optional loss/gpu fields).
- Proposed action contract: knob + target + reason (+ optional chord id), serializable for audit artifacts.
- K8s plan contract: list of objects `{namespace, name, patch}` validated by `_validate_k8s_plan`.
- Artifact contract: every major command writes stable `*_latest.json` and often timestamped history files.

## Extension points for further development
- Add telemetry backend: implement source compatible with `TelemetryCollector`; expose through parser choices and `_collect_observe_samples`.
- Add policy engine: extend `propose_actions` and register parser choice (`--policy`).
- Add safety rule: extend `Guardrails` / approval split, ensure explain + summary surfaces new reason code.
- Add new report type: follow existing pattern (`started_at/finished_at/duration_s`, latest + timestamp, explain events).
- Add k8s object support beyond deployments: evolve plan schema + adapters + verify/apply validators together.

## Source-of-truth files
- `src/modekeeper/cli.py`
- `src/modekeeper/policy/*`
- `src/modekeeper/telemetry/*`
- `src/modekeeper/safety/*`
- `src/modekeeper/adapters/kubernetes.py`
- `tests/test_cli_*.py`, `tests/test_k8s_*.py`, `tests/test_report_contracts.py`
