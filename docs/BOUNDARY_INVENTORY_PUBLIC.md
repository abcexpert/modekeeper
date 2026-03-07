# Public Boundary Inventory (docs)

Scope: `README.md`, top-level `docs/*.md`, and `docs/evidence/**`.
Goal: keep public repo as a verify-first, read-only assessment surface + buyer/procurement evidence; exclude internal-only ops/commercial internals.

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
| `docs/CLI_CONTRACTS.md` | KEEP | Sanitized and merged for public boundary; internal override references removed. |
| `docs/CLI_REFERENCE.md` | KEEP | Sanitized and merged for public boundary; internal override env vars removed. |
| `docs/COMPLIANCE_MATRIX.md` | KEEP | Procurement/security control mapping evidence. |
| `docs/CUSTOM_PASSPORTS.md` | KEEP | Public customer deliverable concept. |
| `docs/DEFINITION_OF_DONE.md` | KEEP | Sanitized and merged for public boundary; aligned to public license+verify model. |
| `docs/DEV_GUIDE.md` | KEEP | Sanitized and merged for public boundary; internal override/gate-server internals removed. |
| `docs/DEV_MINIKUBE_GPU.md` | KEEP | Sanitized and merged for public boundary; internal license mint/rotation detail removed. |
| `docs/DISTRIBUTION_POLICY.md` | KEEP | Canonical boundary policy doc for public/private split. |
| `docs/ENTERPRISE_EVALUATION.md` | KEEP | Buyer-facing enterprise evaluation path. |
| `docs/GETTING_STARTED.md` | KEEP | Public onboarding flow. |
| `docs/HANDOFF.md` | KEEP | Sanitized and merged for public boundary; private paths/vault/server/private repo refs removed. |
| `docs/INDEX.md` | KEEP | Sanitized and merged for public boundary; navigation reflects public-only docs set. |
| `docs/INTERNAL_LICENSE_ISSUANCE.md` | REMOVE | Internal key issuance/kid rotation/operator flow. |
| `docs/K8S_RUNNER_SELF_SERVE.md` | KEEP | Sanitized and merged for public boundary; internal-only wording removed. |
| `docs/OUTREACH_CALL_20MIN.md` | KEEP | Buyer communication asset. |
| `docs/OUTREACH_EMAIL.md` | KEEP | Buyer communication asset. |
| `docs/PASSPORTS.md` | KEEP | Public deliverable concept and boundaries. |
| `docs/PLAYBOOKS.md` | KEEP | Public operational troubleshooting without private infra refs. |
| `docs/PROCUREMENT_PACK.md` | KEEP | Core procurement evidence doc. |
| `docs/PROJECT_MAP.md` | KEEP | Public map of repo/product surfaces. |
| `docs/PROOF_PACKS.md` | KEEP | Evidence catalog; supports buyer/procurement review. |
| `docs/QUICKSTART.md` | KEEP | Canonical public evaluation/start path. |
| `docs/README.md` | KEEP | Public docs index/boundary framing. |
| `docs/RECORD_REPLAY.md` | KEEP | Sanitized and merged for public boundary; public-safe replay guidance retained. |
| `docs/RELEASE.md` | KEEP | Public release boundary and policy. |
| `docs/RELEASE_PROCESS.md` | KEEP | Public release process for read-only snapshot package. |
| `docs/RELEASING.md` | KEEP | Sanitized and merged for public boundary; private repo coupling/internal choreography removed. |
| `docs/ROADMAP_PUBLIC.md` | KEEP | Sanitized and merged for public boundary; no dependency on internal licensing issuance doc. |
| `docs/SAAS_SEAMS.md` | KEEP | Public future-facing architecture seams. |
| `docs/SAFETY_MODEL.md` | KEEP | Public safety framing/evidence context. |
| `docs/SECURITY_POSTURE.md` | KEEP | Security posture evidence for review. |
| `docs/SECURITY_QA.md` | KEEP | Buyer/security Q&A evidence. |
| `docs/SNAPSHOT.md` | KEEP | Sanitized and merged for public boundary; limited to public snapshot context. |
| `docs/STATUS.md` | KEEP | Public progress/status transparency. |
| `docs/SYNTHETIC_PROOFS.md` | KEEP | Public synthetic evidence guidance. |
| `docs/THREAT_MODEL.md` | KEEP | Public security model evidence. |
| `docs/TICKETS.md` | KEEP | Sanitized and merged for public boundary; limited to public roadmap/evaluation-facing tickets. |
| `docs/TODO_BACKLOG.md` | KEEP | Public housekeeping backlog index. |
| `docs/WORKFLOW.md` | KEEP | Sanitized and merged for public boundary; internal key issuance/kid rotation/operator flows removed. |
| `docs/product.md` | KEEP | Public product narrative for assessment surface. |
| `docs/evidence/**` | KEEP | Buyer/procurement evidence artifacts should remain in public snapshot. |

## Cleanup Status

Public boundary cleanup is complete for top-level docs inventory.

- Removed from public repo: `docs/INTERNAL_LICENSE_ISSUANCE.md`, `docs/CHORDS_INTERNAL.md`.
- Previously rewrite-target docs listed above are now sanitized and merged as public-safe `KEEP`.
