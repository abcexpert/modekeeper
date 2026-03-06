# Public Boundary Inventory (docs)

Scope: `README.md`, top-level `docs/*.md`, and `docs/evidence/**`.
Goal: keep public repo as showroom/stub + buyer/procurement evidence; exclude internal-only ops/commercial internals.

| Path | Decision | Rationale |
|---|---|---|
| `README.md` | KEEP | Public entrypoint for evaluation. |
| `docs/APPLY_SPEC.md` | KEEP | Public apply contract/safety semantics. |
| `docs/ARCHITECTURE.md` | KEEP | High-level technical architecture for evaluators. |
| `docs/BUYER_10MIN.md` | KEEP | Buyer-facing evaluation script. |
| `docs/BUYER_JOURNEY.md` | KEEP | Procurement/evaluation narrative. |
| `docs/BUYER_PROOF_PACK.md` | KEEP | Buyer evidence packaging. |
| `docs/BUYER_REQUEST_CHECKLIST.md` | KEEP | Buyer/procurement checklist. |
| `docs/CHORDS.md` | KEEP | Public product behavior model. |
| `docs/CHORDS_INTERNAL.md` | REMOVE | Internal-only by name/content. |
| `docs/CLI_CONTRACTS.md` | REWRITE | Remove internal override references (`MODEKEEPER_PAID`) from public contract wording. |
| `docs/CLI_REFERENCE.md` | REWRITE | Remove internal override env vars from public reference surface. |
| `docs/COMPLIANCE_MATRIX.md` | KEEP | Procurement/security control mapping evidence. |
| `docs/CUSTOM_PASSPORTS.md` | KEEP | Public customer deliverable concept. |
| `docs/DEFINITION_OF_DONE.md` | REWRITE | Contains internal/dev gating flags; align to public license+verify model only. |
| `docs/DEV_GUIDE.md` | REWRITE | Contains internal override/gate-server internals not needed in public snapshot. |
| `docs/DEV_MINIKUBE_GPU.md` | REWRITE | Includes dev license mint/rotation detail beyond public showroom need. |
| `docs/DISTRIBUTION_POLICY.md` | KEEP | Canonical boundary policy doc for public/private split. |
| `docs/ENTERPRISE_EVALUATION.md` | KEEP | Buyer-facing enterprise evaluation path. |
| `docs/GETTING_STARTED.md` | KEEP | Public onboarding flow. |
| `docs/HANDOFF.md` | REWRITE | Keep public buyer-facing handoff; remove private paths/vault/server/private repo refs and internal operator details. |
| `docs/INDEX.md` | REWRITE | Update navigation after boundary cleanup (remove links to removed/internal docs). |
| `docs/INTERNAL_LICENSE_ISSUANCE.md` | REMOVE | Internal key issuance/kid rotation/operator flow. |
| `docs/K8S_RUNNER_SELF_SERVE.md` | REWRITE | Keep runbook but remove internal-only wording (e.g., internal package mirror phrasing). |
| `docs/OUTREACH_CALL_20MIN.md` | KEEP | Buyer communication asset. |
| `docs/OUTREACH_EMAIL.md` | KEEP | Buyer communication asset. |
| `docs/PASSPORTS.md` | KEEP | Public deliverable concept and boundaries. |
| `docs/PLAYBOOKS.md` | KEEP | Public operational troubleshooting without private infra refs. |
| `docs/PROCUREMENT_PACK.md` | KEEP | Core procurement evidence doc. |
| `docs/PROJECT_MAP.md` | KEEP | Public map of repo/product surfaces. |
| `docs/PROOF_PACKS.md` | KEEP | Evidence catalog; supports buyer/procurement review. |
| `docs/QUICKSTART.md` | KEEP | Canonical public evaluation/start path. |
| `docs/README.md` | KEEP | Public docs index/boundary framing. |
| `docs/RECORD_REPLAY.md` | REWRITE | Keep method, but soften insecure demo-specific token/TLS snippets for public snapshot. |
| `docs/RELEASE.md` | KEEP | Public release boundary and policy. |
| `docs/RELEASE_PROCESS.md` | KEEP | Public release process for showroom package. |
| `docs/RELEASING.md` | REWRITE | Keep public release-facing guidance; remove private repo coupling and vendor-internal choreography. |
| `docs/ROADMAP_PUBLIC.md` | REWRITE | Remove link/dependency on internal licensing issuance doc. |
| `docs/SAAS_SEAMS.md` | KEEP | Public future-facing architecture seams. |
| `docs/SAFETY_MODEL.md` | KEEP | Public safety framing/evidence context. |
| `docs/SECURITY_POSTURE.md` | KEEP | Security posture evidence for review. |
| `docs/SECURITY_QA.md` | KEEP | Buyer/security Q&A evidence. |
| `docs/SNAPSHOT.md` | REWRITE | Contains dev/internal continuation and license-rotation implementation detail; keep only public snapshot context. |
| `docs/STATUS.md` | KEEP | Public progress/status transparency. |
| `docs/SYNTHETIC_PROOFS.md` | KEEP | Public synthetic evidence guidance. |
| `docs/THREAT_MODEL.md` | KEEP | Public security model evidence. |
| `docs/TICKETS.md` | REWRITE | Trim internal ops/commercial internals; keep public roadmap/evaluation-facing tickets only. |
| `docs/TODO_BACKLOG.md` | KEEP | Public housekeeping backlog index. |
| `docs/WORKFLOW.md` | REWRITE | Remove internal key issuance/kid rotation/operator dev flows; keep public evaluate/verify/apply boundary view. |
| `docs/product.md` | KEEP | Public product narrative for showroom. |
| `docs/evidence/**` | KEEP | Buyer/procurement evidence artifacts should remain in public snapshot. |

## Priority removal targets (first pass)

1. `docs/INTERNAL_LICENSE_ISSUANCE.md`
2. `docs/CHORDS_INTERNAL.md`

## Priority rewrite targets (second pass)

1. `docs/HANDOFF.md`
2. `docs/RELEASING.md`
3. `docs/WORKFLOW.md`
4. `docs/SNAPSHOT.md`
5. `docs/TICKETS.md`
6. `docs/CLI_REFERENCE.md`
7. `docs/CLI_CONTRACTS.md`
8. `docs/DEV_GUIDE.md`
9. `docs/DEFINITION_OF_DONE.md`
10. `docs/ROADMAP_PUBLIC.md`
11. `docs/INDEX.md`
12. `docs/RECORD_REPLAY.md`
13. `docs/DEV_MINIKUBE_GPU.md`
14. `docs/K8S_RUNNER_SELF_SERVE.md`
