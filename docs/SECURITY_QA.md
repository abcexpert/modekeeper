# Security Questionnaire (RFI Q&A)

Concise answers for Security and Procurement review. This page is link-first and maps each answer to canonical references and procurement-pack artifacts.

## 1) What is the execution model?

ModeKeeper is read-only by default for public workflows (`plan`, `verify`, `export`). Mutation/apply is a separately gated path.

References:
- `docs/SECURITY_POSTURE.md`
- `docs/WORKFLOW.md`
- `report/procurement_pack/buyer_pack/plan/closed_loop_latest.json`
- `report/procurement_pack/buyer_pack/verify/k8s_verify_latest.json`

## 2) What controls gate mutation/apply?

Apply is blocked unless required controls pass (verify gate, kill-switch semantics, and license/entitlement checks). Incident response and gate operations are documented in playbooks.

References:
- `docs/WORKFLOW.md`
- `docs/PLAYBOOKS.md`
- `docs/SECURITY_POSTURE.md`
- `report/procurement_pack/buyer_pack/plan/closed_loop_latest.json`

## 3) What audit/evidence can be provided for review?

Evidence is produced as reproducible artifacts and bundled for buyer review; procurement packaging adds checksums and a deterministic tarball for transfer/integrity checks.

References:
- `docs/BUYER_PROOF_PACK.md`
- `docs/PROCUREMENT_PACK.md`
- `report/procurement_pack/buyer_pack/`
- `report/procurement_pack/checksums.sha256`
- `report/procurement_pack/procurement_pack.tar.gz`

## 4) What supply-chain controls exist for releases?

Public release is wheel-only with explicit release process constraints and wheel-content guardrails; public/private boundary rules are documented and enforced by policy.

References:
- `docs/RELEASE.md`
- `docs/DISTRIBUTION_POLICY.md`
- `report/procurement_pack/docs/RELEASE.md`
- `report/procurement_pack/docs/DISTRIBUTION_POLICY.md`

## 5) How are data, secrets, and credentials handled?

Secrets, keys, licenses, and credentials must not be committed. Runtime/license handling and operational controls are documented in workflow and distribution policy docs.

References:
- `docs/DISTRIBUTION_POLICY.md`
- `docs/WORKFLOW.md`
- `docs/SECURITY_POSTURE.md`
