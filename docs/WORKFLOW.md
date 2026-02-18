# ModeKeeper — workflow (plan-only + verify + paid apply skeleton)

Primary onboarding path for customers: `docs/QUICKSTART.md`.
This document keeps deeper workflow details for developers.

## Dev shell
- `./scripts/dev-shell.sh` — активирует `.venv` и гарантирует, что `mk` в PATH.
- Automation scripts set `DEV_SHELL_QUIET=1` to suppress `mk --help` noise.

## Chord catalog и safety envelope
- Chord в ModeKeeper — это макро-операция (`macro-op`) с инвариантами, а не список фиксированных target-значений.
- Каталог `src/modekeeper/chords/catalog_v1.json` — authoritative-источник guardrails: описывает `intent`, `risk_tier`, `required_signals`, `invariants`, `knobs_touched`, а также скелетные `cooldown_ms`/`budget`.
- Safety envelope при split/apply действий:
  - неизвестный `action.chord` блокируется с причиной `unknown_chord`;
  - chord с `risk_tier="advanced"` требует `--approve-advanced`, иначе блокируется с причиной `approval_required`.
- Как добавить новый chord:
  - добавить запись в `src/modekeeper/chords/catalog_v1.json` (только метаданные, без target-значений);
  - если chord advanced, выставить `risk_tier: "advanced"`;
  - прогнать валидацию каталога.
- Валидация каталога:
  - `./.venv/bin/mk chords validate --catalog src/modekeeper/chords/catalog_v1.json --out report/_chords_validate`
  - отчёт: `report/_chords_validate/chords_validate_latest.json`.

## End-to-end (safe, plan-only)
### 0) Bootstrap kind/e2e
- `./scripts/kind-bootstrap.sh`

### 1) Dev shell
- `./scripts/dev-shell.sh`

### 2) Generate plan (closed-loop dry-run)
- `./.venv/bin/mk closed-loop run --scenario drift --dry-run --out report/_cl`

Artifacts in `report/_cl`:
- `explain.jsonl`
- `closed_loop_<timestamp>.json`, `closed_loop_latest.json`
- `policy_bundle_latest.json` (какая policy использована + provenance)
- `summary.md`
- `k8s_plan.json`, `k8s_plan.kubectl.sh` (**не выполняется**)

### Policy bundle v1 (provenance + rollback plumbing)
- `policy_bundle_latest.json` — детерминированный артефакт `policy_bundle.v1` с фиксированными ключами (`sort_keys`) о том, **какая policy** была использована.
- `provenance` нужен для трассировки происхождения решения: версия ModeKeeper, git commit/dirty и host.
- Артефакт пишется в `--out` для:
  - `mk closed-loop run`
  - `mk k8s apply`
- Rollback в v1 — только plumbing/skeleton:
  - если в `--out` есть verify-отчёт (`k8s_verify_latest.json`), создаётся `rollback_plan_latest.json`;
  - bundle получает ссылки `rollback.from_verify_report` и `rollback.rollback_plan_path`;
  - полноценный rollback apply/enforcement пока не включён.

### 2a) Observe from k8s logs (kind)
Example:
```
./.venv/bin/mk observe --source k8s --k8s-namespace default --k8s-deployment trainer --container trainer --duration 2m --out report/_observe_k8s
```

### 2b) Continuous controller (watch)
`mk closed-loop watch` runs the closed-loop repeatedly and writes per-iteration artifacts into `iter_0001/`, `iter_0002/`, ...

Example:
```
./.venv/bin/mk closed-loop watch --scenario drift --dry-run --out report/_watch --interval 30s
```

Artifacts in `report/_watch`:
- `iter_0001/`, `iter_0002/`, ... (each contains the same artifacts as `closed-loop run`)
- `watch_latest.json` (session rollup: iterations_done, last_iteration_out_dir, aggregated counts)
- `watch_summary.md` (tiny human-readable rollup)

## Paid (recommended, one-shot closed-loop apply)
`mk closed-loop run --apply` выполняет verify + apply в одном шаге, но строго gated:
- `MODEKEEPER_KILL_SWITCH=1` → apply блокируется.
- Kill-switch имеет максимальный приоритет: `MODEKEEPER_INTERNAL_OVERRIDE=1` и валидная лицензия не обходят блокировку.
- При `MODEKEEPER_KILL_SWITCH=1` CLI apply-entrypoints (`mk closed-loop run --apply`, `mk closed-loop watch --apply`, `mk k8s apply`) завершаются с `exit code 2` и однострочной ошибкой: `ERROR: MODEKEEPER_KILL_SWITCH=1 blocks apply/mutate operations`.
- Лицензия ищется в детерминированном порядке:
  1. `--license-path` (CLI), если задан
  2. `MODEKEEPER_LICENSE_PATH` (env)
  3. `./modekeeper.license.json` в текущей директории (последний fallback)
- лицензия не найдена → apply блокируется (`license_missing`).
- нет entitlement `apply` в лицензии → apply блокируется (`entitlement_missing`).
- Free mode остаётся read-only (`plan/verify/watch`), paid mode разрешает `apply/autotune` только при валидной лицензии с entitlement `apply`.
- apply requires `verify_ok=true`; otherwise `exit code 2` + fixed stderr: `ERROR: verify_ok=true is required for apply/mutate operations`.

`closed_loop_latest.json` fields for `closed-loop run --apply`:
- `verify_ok` (bool)
- `apply_attempted` (bool)
- `apply_ok` (bool, when attempted)
- `apply_blocked_reason` (string|null)
- `k8s_verify_report_path` (string path)
- `k8s_apply_report_path` (string path|null)
- `results` length equals `proposed` length even when blocked
- `apply_decision_summary` (optional/legacy)

Для демо безопасный дефолт: `MODEKEEPER_KILL_SWITCH=1` (apply блокируется). Для реального apply отключите kill switch: `MODEKEEPER_KILL_SWITCH=0` (или unset).

### Canonical paid e2e (kind)

DoD-grade golden-path e2e: **paid + apply** on kind (no jq).

**Prereqs (host):**
- Docker daemon available (kind uses Docker)
- `kind`, `kubectl`, `helm` in `$PATH`
- repo `.venv` exists and contains `./.venv/bin/mk` and `./.venv/bin/python` (script requires it)

**Run:**
- `./scripts/e2e-apply-kind.sh`

**What it validates:**
- mints dev license into `report/_e2e_apply_kind/` and exports `MODEKEEPER_LICENSE_*`
- runs `mk closed-loop run --apply` and asserts on `report/_e2e_apply_kind/closed_loop_latest.json` (Python, no jq)
- trainer log observation is resilient to rolling updates / pod replacement:
  - waits for Ready pods after rollout
  - scans all candidate pods (ready+running first), uses `--previous` when needed
  - PASS when `modekeeper/knob.grad_accum_steps=8` is observed

**Outputs:**
- `report/_e2e_apply_kind/closed_loop_latest.json`
- `report/_e2e_apply_kind/deploy_before.json`, `deploy_after.json`
- `report/_e2e_apply_kind/license_dev.json`, `license_dev_public_keys.json`

### Mint dev license

```bash
./bin/mk-mint-dev-license
```
### One-command k8s drift demo

```bash
./bin/mk-demo-k8s-drift
# keep dev license files:
./bin/mk-demo-k8s-drift --keep-license
# keep trainer deployment/resources after demo cleanup:
./bin/mk-demo-k8s-drift --keep-deploy
# keep both:
./bin/mk-demo-k8s-drift --keep-license --keep-deploy
```

### One-command sales demo (developer/WSL only)

```bash
./bin/mk-demo-sales
# keep trainer deployment/resources after demo cleanup:
./bin/mk-demo-sales --keep-deploy
# keep dev license files after demo cleanup:
./bin/mk-demo-sales --keep-license
```

### One-command safety gates demo (non-mutating)

```bash
./bin/mk-demo-safety-gates
```

Demonstrates deterministic blocked apply cases:
- A) missing license path -> `license_invalid`
- B) unknown `kid` in keyring -> `license_invalid`
- C) failing verify artifact (`verify_ok=false`) -> `verify_failed` (apply blocked by core `mk k8s apply` gate)
- D) `MODEKEEPER_KILL_SWITCH=1` -> `kill_switch` (`rc=2` + fixed error line)

Artifacts are saved under `report/_demo_safety_gates` (or `--out DIR`), one subdirectory per case.


Verify:

```bash
MODEKEEPER_LICENSE_PUBLIC_KEYS_PATH=./license_dev_public_keys.json KUBECTL="$PWD/bin/kubectl-mk-gpu" ./.venv/bin/mk license verify --license ./license_dev.json --out report/_license_dev_verify
```

Apply:

```bash
MODEKEEPER_LICENSE_PUBLIC_KEYS_PATH=./license_dev_public_keys.json MODEKEEPER_LICENSE_PATH=./license_dev.json KUBECTL="$PWD/bin/kubectl-mk-gpu" ./.venv/bin/mk closed-loop run --scenario drift --apply --out report/_cl_k8s_apply_paid
```
### License key rotation (kid)
- Формат keyring: JSON map `{ "kid": "pubkey_b64_raw32", ... }` (allowlist).
- В `license.v1` поле `kid` подписывается вместе с payload: менять `kid` после подписи нельзя.
- Verify:
  - `kid` задан: берётся только ключ этого `kid`; неизвестный `kid` => `license_invalid`.
  - `kid` не задан: fallback, verify может перебрать все allowlisted ключи; если ни один не подошёл => `license_invalid`.
- Ротация: добавить новый `{kid -> pubkey}` в keyring, выпускать новые лицензии с новым `kid`, старые лицензии продолжают работать, пока их `kid` остаётся в allowlist.

### Canonical kind/e2e scripts
```
./scripts/e2e-smoke-kind.sh
```
Safe: kill switch blocks apply.

```
./scripts/e2e-apply-kind.sh
```
Real `kubectl` patches.

### Real apply (kind)

Use the canonical paid e2e above — it performs real apply on kind and includes all checks:

- `./scripts/e2e-apply-kind.sh`

### 3) Render kubectl script (no execution)
- `./.venv/bin/mk k8s render --plan report/_cl/k8s_plan.json --out report/_render`

Artifacts in `report/_render`:
- `explain.jsonl`
- `k8s_plan.kubectl.sh`
- `k8s_render_<timestamp>.json`, `k8s_render_latest.json`

### 4) Verify plan against cluster (no changes)
Важно: `mk k8s apply` читает verify-отчёт рядом с `--plan`, поэтому verify нужно писать в ту же директорию, где лежит plan.
- `./.venv/bin/mk k8s verify --plan report/_cl/k8s_plan.json --out report/_cl`

Artifacts in `report/_cl` (добавятся):
- `k8s_verify_<timestamp>.json`, `k8s_verify_latest.json`

### 5) Apply (paid)
Требуется `verify_ok=true` (в `report/_cl/k8s_verify_latest.json`).

Пример:
- `./.venv/bin/mk license verify --license ./license.json --out report/_license_verify`
- `MODEKEEPER_LICENSE_PATH=./license.json ./.venv/bin/mk k8s apply --plan report/_cl/k8s_plan.json --out report/_apply`

Artifacts in `report/_apply`:
- `explain.jsonl`
- `k8s_apply_<timestamp>.json`, `k8s_apply_latest.json`
- `policy_bundle_latest.json` (policy bundle v1)
- exit code: `0` (success) / `1` (apply failed) / `2` (blocked or plan errors)
`k8s_apply_latest.json` stores per-item apply results under canonical `.checks.items[]`; convenience alias: top-level `.items` (same content).
Minimal check:
```bash
jq '{ok, items_n: ((.items // .checks.items // [])|length), failed_items_n: ((.items // .checks.items // [])|map(select(.ok!=true))|length)}' report/_cl_paid/k8s_apply_latest.json
```

## Notes
- `k8s/trainer-minimal.yaml` + pod-template annotations — механизм observability: именно эти knobs попадают в логи.
- Heterogeneous clusters:
  - ModeKeeper works on mixed nodes/GPUs, but `observe`/`closed-loop` reports now include `environment` with `unstable=true` when >1 node or >1 GPU model is observed in the sample window.
  - Для более стабильных рекомендаций и воспроизводимости закрепляйте workload на однородном пуле:
    - `nodeSelector` (жёсткий pin на label),
    - `affinity.nodeAffinity` (required/preferred placement rules).
- Все отчёты используют v0 report contract: `schema_version=="v0"` (str) и `duration_s` int(datetime diff).
- Контракты артефактов/событий: `docs/CLI_CONTRACTS.md`
- Incident runbooks: `docs/PLAYBOOKS.md`
- Тикеты: `docs/TICKETS.md`
