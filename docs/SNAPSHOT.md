# ModeKeeper — Snapshot для продолжения (K8s plan-only + verify + product docs)

> Цель: один переносимый документ в репозитории, чтобы продолжать работу без контекста чатов.
> Дефолт продукта: **plan-only + verify** (ничего не меняет). Платный режим: apply только под лицензией и после verify-ok.

## Links
- PyPI: `modekeeper`
- GitHub: `abcexpert/modekeeper`
- Current state (exec): `docs/STATUS.md`

## 0) Контекст и дефолт-режим
- **Free:** observe + closed-loop dry-run + k8s render/verify (**ничего не меняет**).
- **Paid:** one-shot `closed-loop run --apply` (рекомендуется), gated: kill-switch + license + **verify-ok**.

## 0.1) Canonical kind/e2e bootstrap
- Step 0: `./scripts/kind-bootstrap.sh`
- Step 1: `./scripts/dev-shell.sh`
- Step 2+: recommended `mk closed-loop run --apply` (paid) or manual steps (closed-loop run, k8s verify, paid apply).

Observability: `k8s/trainer-minimal.yaml` + pod-template annotations — это механизм knobs, которые читаются в логах.

Canonical kind/e2e scripts:

Dev paid demo (repo-local dev license):
- `./bin/mk-mint-dev-license` (пишет `license_dev.json` + `license_dev_public_keys.json`)
- `./bin/mk-demo-k8s-drift` (E2E drift→apply; `--keep-license` чтобы не удалять файлы)

License keyring/rotation contract:
- keyring format: JSON map `{ "kid": "pubkey_b64_raw32", ... }`.
- `kid` is signed as part of `license.v1` payload.
- verify semantics: known `kid` -> only that key; unknown `kid` -> `license_invalid`; no `kid` -> allowlist fallback.
- rotation: add new key+`kid`, mint new licenses with it, keep old `kid` in allowlist during migration window.

- `./scripts/e2e-smoke-kind.sh` (safe: kill switch blocks apply)
- `./scripts/e2e-apply-kind.sh` — canonical DoD-grade paid e2e apply on kind (Docker+kind+Helm+kubectl): mints dev-license into `report/_e2e_apply_kind/`, runs `mk closed-loop run --apply`, asserts `closed_loop_latest.json`, and verifies trainer logs contain `modekeeper/knob.grad_accum_steps=8` (resilient to pod rollout/replacement).

Note: automation scripts set `DEV_SHELL_QUIET=1` to suppress `mk --help` noise.

## 1) Реализовано и работает

### 1.1 CLI / команды
- `mk k8s render --plan PATH --out OUT`
  - `--plan` обязателен (JSON list items как `k8s_plan.json`)
  - генерирует `out/k8s_plan.kubectl.sh` + отчёт `k8s_render_*.json` и `k8s_render_latest.json`
  - **kubectl не выполняется**
- `mk k8s verify --plan PATH --out OUT` (**plan-only, без изменений**)
  - формат входа как у render; валидация та же
  - проверяет:
    - `kubectl config current-context` (не hard fail; отражается в отчёте)
    - per-item:
      - `kubectl get namespace/<ns> -o name`
      - `kubectl -n <ns> get deployment/<name> -o name`
      - dry-run patch: `--dry-run=server`
  - пишет отчёт `k8s_verify_*.json` и `k8s_verify_latest.json`
  - на ошибках чтения/валидации плана: rc=2 и **без отчёта** (только explain.jsonl), как в render

### 1.2 Контракты планов
- План = JSON list items вида:
  - `{"namespace": <non-empty str>, "name": <non-empty str>, "patch": <dict or null>}`
- `_validate_k8s_plan(plan)`:
  - item dict
  - `namespace` non-empty str
  - `name` non-empty str
  - `patch` dict (или отсутствует/None → `{}`)
- invalid_item → explain `kind=invalid_item index=<idx>` + rc=2 + **без частичных артефактов**

### 1.3 Артефакты
- `closed-loop run` (plan-only артефакты):
  - `k8s_plan.json`
  - `k8s_plan.kubectl.sh` (**не выполняется**)
  - в `closed_loop_latest.json`: `k8s_plan_path`, `k8s_plan_items`, `k8s_kubectl_plan_path`, `k8s_namespace`, `k8s_deployment`
- `closed-loop run --apply` (paid, one-shot):
  - дополнительно пишет `k8s_verify_*.json` и `k8s_apply_*.json` (если apply разрешен)
  - `k8s_apply_latest.json` хранит per-item результаты apply в canonical `.checks.items[]`; convenience alias: top-level `.items` (same content)
  - в `closed_loop_latest.json`:
    - `verify_ok` (bool)
    - `apply_attempted` (bool)
    - `apply_ok` (bool, when attempted)
    - `apply_blocked_reason` (string|null)
    - `k8s_verify_report_path` (string path)
    - `k8s_apply_report_path` (string path|null)
    - `results` length equals `proposed` length even when blocked
    - `apply_decision_summary` (optional/legacy)
- `k8s render`:
  - explain events: `k8s_render_start`, `k8s_kubectl_plan_written`, `k8s_render_report`, `k8s_render_error`
  - `k8s_plan.kubectl.sh` bash-safe (экранирование `'` внутри JSON), newline в конце, chmod 755
- `k8s verify`:
  - explain events: `k8s_verify_start`, `k8s_verify_checked{items,ok}`, `k8s_verify_report`, `k8s_verify_error`
  - поля `k8s_verify_latest.json`:
    - `k8s_plan_path`, `k8s_plan_items`, `k8s_namespace`/`k8s_deployment` (`mixed` если разные)
    - `kubectl_context` (или null)
    - `checks.kubectl_present` (kubectl найден ли; можно подменить env `KUBECTL=/path/to/kubectl`)
    - `checks.current_context` (rc/ok/stderr)
    - `checks.items[]`: `namespace_exists`, `deployment_exists`, `dry_run{attempted,mode,ok,rc,stderr}`
    - `ok` (true только если kubectl есть и все required checks прошли)


**Audit decision trace (MK-075):**
- `decision_trace_latest.jsonl` — decision trace по тикам (JSONL), schema `decision_trace_event.v0`.
- В `closed_loop_latest.json`: `audit_trace: {path: "decision_trace_latest.jsonl", schema_version: "decision_trace_event.v0"}`.

### 1.4 Tests
- `tests/conftest.py`:
  - bootstrap `src/` в `sys.path` (src-layout)
  - `mk_path` fixture: предпочитает `.venv/bin/mk`, иначе `mk` из PATH
- Render tests: `tests/test_k8s_render.py`, `tests/test_k8s_render_errors.py`
- Verify tests: `tests/test_k8s_verify.py`, `tests/test_k8s_verify_errors.py`
- `pytest -q` зелёный.

## 2) Документация
- `docs/GETTING_STARTED.md`: canonical onboarding recipe (customer-facing, copy/paste, read-only).
- `README.md`: добавлен product-intro (“Для кого и зачем”) + ссылка на `docs/product.md`.
- `docs/product.md`: ICP/боли/ценность/free vs paid/безопасность/quickstart/ограничения.
- CLI contracts (artifacts + explain events): docs/CLI_CONTRACTS.md

## Метод: аккорды и паспорта
- v1 auto: только safe chords (`NORMAL-HOLD`, `DRIFT-RETUNE`, `BURST-ABSORB`, `INPUT-STRAGGLER`, `RECOVER-RELOCK`).
- advanced chords (`COMM-CONGESTION`, `NEAR-HANG/TIMEOUT-GUARD`): off-by-default до появления нужной телеметрии и явного разрешения профиля.
- дефолт продукта без изменений: `plan-only + verify`; apply остаётся gated (paid + verify-ok + safety checks).
- паспорта - следующий этап runtime-включения, но требования, ограничения и клиентские примеры уже зафиксированы.

См. детали: `docs/CHORDS.md` и `docs/PASSPORTS.md`.

## DONE (offline / no real k8s cluster)
- Record/replay playbook: `docs/RECORD_REPLAY.md`.
- Golden traces under `tests/data/observe/`: `stable`, `bursty`, `sparse`, `out_of_order`, `corrupted`, `duplicates`, `clock_skew`, `realistic_dirty`.
- Dirty log tolerance + `observe_ingest` counters persisted per run and aggregated in watch.
- `verify_blocker` in `mk k8s verify` reports with deterministic priority.
- Verify diagnostics RBAC signals: `auth_can_i_patch_deployments`, `auth_can_i_get_deployments`.
- Watch UX: `artifact_paths` in `watch_latest.json` + pointer lines in `watch_summary.md` with consistent null semantics.
- Raw recording flags (`mk observe --record-raw`, `mk closed-loop run/watch --observe-record-raw`) + report fields and best-effort error behavior.
- GPU telemetry ingest in observe/closed-loop artifacts (`telemetry.points` with `ts_ms`, latency/loss and optional GPU fields) + reliable watch shutdown/final artifact flush.

## Backlog
- Единственный backlog и статусы: `docs/TICKETS.md` (source of truth).
- `docs/SNAPSHOT.md` не ведёт список задач; это только “как продолжать/запускать”.
