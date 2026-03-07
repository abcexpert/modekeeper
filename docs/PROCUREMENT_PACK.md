# Procurement Pack

## Purpose

Procurement/RFI Pack is a one-command, shareable procurement bundle for enterprise review. It packages verify-first read-only assessment outputs for Kubernetes/GPU cost and risk, together with core policy/workflow docs and reproducible metadata.
This output is `report/procurement_pack/**` and is distinct from `mk export handoff-pack`.

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

Buyer-pack export artifacts are included under `report/procurement_pack/buyer_pack/export/` (for example: `bundle_manifest.json`, `bundle.tar.gz`, `bundle_summary.md`).

## Verify checksums

```bash
cd report/procurement_pack && sha256sum -c checksums.sha256
```

The verification should complete with no `FAILED` lines.

Execution remains customer-managed; this pack is for review and handoff, not vendor-operated runtime changes.
As of `v0.1.33`, the public core is the frozen baseline; replay proof depth has increased without widening public product surface.

Current proof-layer replay status on `main`:
- `scripts/proof-matrix-replay.sh` is replayable end-to-end.
- `replica_overprovisioning`, `cpu_pressure`, and `memory_pressure` pass (3/3).
- This evidence strengthens verify-first read-only due diligence via deterministic replay.

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
