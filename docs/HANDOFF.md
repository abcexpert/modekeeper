# HANDOFF

## Elevator pitch
ModeKeeper — verify-first агент для Kubernetes/ML-окружений: по умолчанию только read-only наблюдение, план и проверка, без мутаций.
Продукт закрывает риск «автотюна без контроля» через жёсткие safety-gates перед любым apply.
Enterprise получает детерминированные артефакты (JSON/MD), decision trace и проверяемый audit trail для change-control.
Коммерческий путь разделён: public surface для безопасного eval/onboarding, private surface для PRO-функций и поставки.
Apply включается только при лицензии и после verify-ok; kill-switch остаётся абсолютным блокером.
Это позволяет запускать пилот быстро, но с контрактами безопасности и поставки, пригодными для procurement/security review.

## Где что лежит
- Public repo (showroom/stub): `/home/oleg/code/modekeeper`
- Private repo (PRO/commercial): `/home/oleg/code/modekeeper-private`

Ключевые директории:
- Public core code: `/home/oleg/code/modekeeper/src/modekeeper/`
- Private core code: `/home/oleg/code/modekeeper-private/src/modekeeper/`
- Public docs/evidence: `/home/oleg/code/modekeeper/docs/`, `/home/oleg/code/modekeeper/docs/evidence/`
- Private docs/evidence: `/home/oleg/code/modekeeper-private/docs/`, `/home/oleg/code/modekeeper-private/docs/evidence/`
- Public scripts/release: `/home/oleg/code/modekeeper/scripts/`
- Private service/release helpers: `/home/oleg/code/modekeeper-private/bin/`, `/home/oleg/code/modekeeper-private/tools/systemd/`

CLI entrypoints:
- Console entrypoint (оба репо): `mk = modekeeper.cli:main` (`pyproject.toml`)
- Public installer/onboarding: `/home/oleg/code/modekeeper/bin/mk-install`, `/home/oleg/code/modekeeper/bin/mk-doctor`, `/home/oleg/code/modekeeper/bin/mk-enterprise-eval`
- Private ops/release: `/home/oleg/code/modekeeper-private/bin/mk-release-stub`, `/home/oleg/code/modekeeper-private/bin/mk-procurement-pack`, `/home/oleg/code/modekeeper-private/bin/mk-license-issue`, `/home/oleg/code/modekeeper-private/bin/mk-license-revoke`

## Что читать (порядок)
1. `/home/oleg/code/modekeeper/docs/SNAPSHOT.md`
2. `/home/oleg/code/modekeeper/docs/TICKETS.md`
3. `/home/oleg/code/modekeeper/docs/DEFINITION_OF_DONE.md`
4. `/home/oleg/code/modekeeper/docs/RELEASING.md`

Для private ветки работ после этого:
1. `/home/oleg/code/modekeeper-private/docs/SNAPSHOT.md`
2. `/home/oleg/code/modekeeper-private/docs/TICKETS.md`
3. `/home/oleg/code/modekeeper-private/docs/DEFINITION_OF_DONE.md`
4. `/home/oleg/code/modekeeper-private/docs/RELEASE.md`

## Статус сейчас
- Public last tag: `v0.1.29` (из `git describe --tags --abbrev=0` в `/home/oleg/code/modekeeper`)
- Public project version: `0.1.29` (`/home/oleg/code/modekeeper/pyproject.toml`)
- Canonical release command (one-button, public+private):
  - из `/home/oleg/code/modekeeper`: `./scripts/mk-release-all.sh`
- Public-only release command:
  - из `/home/oleg/code/modekeeper`: `./scripts/release_public.sh`

## План до enterprise-ready
Источник: `docs/TICKETS.md`.

Важно: в public `/home/oleg/code/modekeeper/docs/TICKETS.md` сейчас нет `TODO/INPROGRESS` (все тикеты `DONE`).
Ниже — оставшиеся `TODO` из private `/home/oleg/code/modekeeper-private/docs/TICKETS.md`, отсортированные по зависимости `license → safety → audit → bundles → e2e/export/docs`.

### License
- `MK-129` — Phase-3: Licensing v2 trust chain (root -> issuer) — tooling + enforcement
  - Status: `TODO`
  - DoD-смысл: ввести обязательную trust-chain проверку (root→issuer) в license/apply gates, включая rotation/revocation semantics.
  - Evidence: `docs/evidence/mk129_license_trust_chain/` (stub: `trust_chain_bundle_latest.json`, `license_verify_chain_latest.json`, `rotation_drill.md`)

### Safety
- `MK-123` — Phase-3: Quarantine/Isolation v1 — read-only detection + recommended plan + safe apply constraints
  - Status: `TODO`
  - DoD-смысл: добавить quarantine/isolation detection в read-only фазе и блок/ограничения apply до условий выхода.
  - Evidence: `docs/evidence/mk123_quarantine/` (stub: `quarantine_detect_latest.json`, `isolation_plan_latest.json`, `gate_blocked_example.json`)
- `MK-124` — Phase-3: Apply v1 controls — knobs + guardrails + cooldown enforcement
  - Status: `TODO`
  - DoD-смысл: зафиксировать и enforce-ить apply controls (bounds/guardrails/cooldown) с детерминированными reason-кодами.
  - Evidence: `docs/evidence/mk124_apply_controls/` (stub: `apply_controls_latest.json`, `cooldown_blocked.json`, `contract_diff.md`)
- `MK-125` — Phase-3: Apply v1 resilience — verify-after-apply + auto-rollback + decision trace contract
  - Status: `TODO`
  - DoD-смысл: после apply всегда делать verify-after-apply и запускать auto-rollback при fail, с обязательными trace events.
  - Evidence: `docs/evidence/mk125_apply_resilience/` (stub: `verify_after_apply_latest.json`, `rollback_attempt_latest.json`, `decision_trace_slice.jsonl`)

### Audit
- `MK-122` — Phase-3: Release policy (private) — GitHub Releases notes-only + links to vault deliverables
  - Status: `TODO`
  - DoD-смысл: закрепить private release policy (notes-only + vault links) и policy-check на отсутствие binary attachments.
  - Evidence: `docs/evidence/mk122_private_release_policy/` (stub: `release_notes_template.md`, `policy_check.log`, `vault_verify_transcript.txt`)

### Bundles
- `MK-127` — Phase-3: Standard procurement pack v2 — deterministic contract + acceptance checklist
  - Status: `TODO`
  - DoD-смысл: сделать v2 контракт procurement pack обязательным и валидируемым перед упаковкой.
  - Evidence: `docs/evidence/mk127_procurement_v2/` (stub: `procurement_contract_v2.md`, `acceptance_checklist_latest.json`, `procurement_pack_manifest.json`)
- `MK-126` — Phase-3: Customer passport deliverable v1 — template/checklist contract
  - Status: `TODO`
  - DoD-смысл: стандартизировать customer passport handoff (template + validator + compatibility matrix).
  - Evidence: `docs/evidence/mk126_passport_deliverable/` (stub: `passport_template_v1.md`, `passport_checklist_latest.json`, `passport_pack_manifest.json`)

### E2E / Export / Docs
- `MK-128` — Phase-3: Evaluation kit v1 — 10-min demo scenario + evidence pointers
  - Status: `TODO`
  - DoD-смысл: собрать детерминированный 10-минутный eval-kit с индексом evidence-артефактов и readiness-check.
  - Evidence: `docs/evidence/mk128_eval_kit/` (stub: `demo_10min_script.md`, `eval_index_latest.md`, `readiness_check.log`)

Отдельно (POST, после core commercial-finish):
- `MK-130` — Multi-cluster inventory/ROI federation pack — `TODO`, помечен как `Phase-3 (POST)`.

## abc2 server/vault/backups
- Working copies pattern on abc2: `/root/modekeeper*`
  - confirmed from docs: `/root/modekeeper-private`
- Bare remotes pattern on abc2: `/home/oleg/*.git`
  - confirmed from docs: `/home/oleg/modekeeper-private-remote.git`
- Vault pattern: `<VAULT_PATH>/*`
  - confirmed from docs: `<VAULT_PATH>/licenses/issuer_keys/`, `<VAULT_PATH>/licenses/ops/`, `<VAULT_PATH>/procurement_pack/`, `<VAULT_PATH>/releases/signing_keys/`
- Backups pattern: `/root/backups/*`
  - confirmed from docs: `/root/backups/modekeeper-private/`

Правило: никогда не пушить vault (ни содержимое `<VAULT_PATH>/*`, ни любые секреты/ключи из vault в git/PyPI/GitHub Releases).

## Next action
- Next action: `MK-129` (Licensing v2 trust chain) — верхний приоритет по зависимости `license -> ...`.
- CHECK перед стартом фикса:
  - подтверждён source-of-truth: `/home/oleg/code/modekeeper-private/docs/TICKETS.md` (тикет `MK-129` всё ещё `TODO`);
  - есть отдельные тест-кейсы на `valid chain / unknown issuer / expired issuer cert / revoked issuer`;
  - не используются и не коммитятся реальные vault-ключи (`<VAULT_PATH>/**` только runtime/ops, не git);
  - контракт ошибок gate детерминирован (reason-коды и non-zero exit) и совместим с текущими `license/apply` entrypoints.
