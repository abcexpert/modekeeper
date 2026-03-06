# Procurement/RFI Pack

## Purpose

Procurement/RFI Pack is a one-command, shareable change-ready handoff pack for enterprise review. It packages verify-first read-only assessment outputs for Kubernetes/GPU cost and risk, together with core policy/workflow docs and reproducible metadata.

## Run this

```bash
./bin/mk-procurement-pack
```

Output root: `report/procurement_pack`.

## What to send

Send these artifacts together:

- `report/procurement_pack/procurement_pack.tar.gz`
- buyer-pack manifest artifacts under `report/procurement_pack/buyer_pack/`
- `report/procurement_pack/checksums.sha256`

## Verify checksums

```bash
cd report/procurement_pack && sha256sum -c checksums.sha256
```

The verification should complete with no `FAILED` lines.

Execution remains customer-managed; this pack is for review and handoff, not vendor-operated runtime changes.

## Checklist

Use these canonical references during review:

- Buyer evidence flow: `docs/BUYER_PROOF_PACK.md`
- Security posture map: `docs/SECURITY_POSTURE.md`
- Compliance matrix: `docs/COMPLIANCE_MATRIX.md` (included in `report/procurement_pack/docs/`)
- Security questionnaire (RFI Q&A): `docs/SECURITY_QA.md` (included in `report/procurement_pack/docs/`)
- Threat model: `docs/THREAT_MODEL.md` (included in `report/procurement_pack/docs/`)
- Workflow and gate behavior: `docs/WORKFLOW.md`
- Release guardrails: `docs/RELEASE.md`
- Distribution boundary policy: `docs/DISTRIBUTION_POLICY.md`
