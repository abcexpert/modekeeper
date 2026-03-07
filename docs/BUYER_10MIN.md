# BUYER_10MIN

10-minute first-contact script for buyer/procurement/security: what to run, what to verify, and what can/cannot be claimed from public evidence.

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

- Verify first: check integrity first, then review artifacts.
- Canonical public workflow: `observe -> plan -> verify -> export`.
- Public core is strict read-only assessment for Kubernetes/GPU cost and risk before any mutate/apply decision.
- Procurement pack is artifact packaging/transfer, not a separate product workflow.
- Integrity is explicit and testable via `sha256sum -c checksums.sha256`.
- `apply` is separately licensed/gated and not baseline public evaluation.
- Runtime boundary is customer-managed (customer environment, customer controls).

## 6) First-contact claims boundary

Say in first contact:
- Public core baseline is frozen at `v0.1.33`.
- Post-baseline replayable proof tranche passes 3/3 scenarios on current `main` using `scripts/proof-matrix-replay.sh`: `replica_overprovisioning`, `cpu_pressure`, `memory_pressure`.
- Evidence is reproducible for that published matrix and supports verify-first claims.

Do not say in first contact:
- Universal/exhaustive detection coverage across all workloads/environments.
- Guaranteed savings or guaranteed risk reduction.
- Vendor-operated/autonomous production execution.
- Public availability of apply/implementation capabilities.
- Any expansion of public product surface beyond frozen public core.

## 7) PRO note

PRO-релизы в публичных каналах идут как notes-only.
Доставка делается через vendor-provided stamp + transcripts + SHA256.
Проверка: прогон bash transcript и `sha256sum -c` по переданному manifest.
