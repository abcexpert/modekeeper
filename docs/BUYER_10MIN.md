# BUYER_10MIN

Скрипт на 10 минут для buyer/procurement/security: что запустить, что получить, что показать и как проверить.

## 1) Prereqs

- `bash`, `tar`, `sha256sum`
- Локальная копия этого репозитория
- Около 10 минут на проверку

## 2) Run (1 command)

```bash
./bin/mk-procurement-pack
```

## 3) Verify (1 command)

```bash
cd report/procurement_pack && sha256sum -c checksums.sha256
```

## 4) What to open

Внутри `report/procurement_pack` откройте в таком порядке:

- [Buyer request checklist (pilot intake)](BUYER_REQUEST_CHECKLIST.md)
- `docs/SECURITY_POSTURE.md` (модель безопасности и границы)
- `docs/WORKFLOW.md` (end-to-end поток и gate'ы)
- `docs/COMPLIANCE_MATRIX.md` (маппинг контролей)
- `docs/SECURITY_QA.md` (ответы security)
- `docs/RELEASE.md` (как оформляется релиз и evidence)
- `docs/DISTRIBUTION_POLICY.md` (правила публичной/приватной доставки)
- `buyer_pack/plan/closed_loop_latest.json` (`verify_ok`, `kill_switch_active`, `apply_blocked_reason`, `entitlements_summary`)
- `buyer_pack/verify/k8s_verify_latest.json` (статус verify и блокеры)
- `buyer_pack/plan/decision_trace_latest.jsonl` + `buyer_pack/plan/explain.jsonl` (audit trail)
- `buyer_pack/export/bundle_manifest.json` + `buyer_pack/export/bundle.tar.gz` + `buyer_pack/export/bundle_summary.md` (состав и упаковка экспортного бандла)

## 5) Talking points

- Сначала verify, потом доверие: сначала проверяем целостность, потом читаем артефакты.
- Один канонический путь: только procurement pack, в нём уже есть buyer artifacts и manifest с checksum.
- Артефакты детерминированы: структура стабильная и проверяемая.
- Целостность проверяется явно: `sha256sum -c checksums.sha256`.
- По умолчанию режим read-only.
- `apply` жёстко gated и блокируется, если условия не выполнены.
- Kill-switch абсолютный и останавливает apply.
- `decision_trace` и `explain` дают полноценный audit trail.

## 6) PRO note

PRO-релизы в публичных каналах идут как notes-only.
Доставка делается через vendor-provided stamp + transcripts + SHA256.
Проверка: прогон bash transcript и `sha256sum -c` по переданному manifest.
