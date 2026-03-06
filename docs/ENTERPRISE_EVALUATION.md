# Enterprise Evaluation (30-60 Minutes)

Use this path for a fast enterprise review of a verify-first, read-only assessment for Kubernetes/GPU cost and risk, with customer-managed execution, link-first evidence, and a change-ready handoff pack.

## Run

```bash
./bin/mk-enterprise-eval
```

This creates:

- `report/procurement_pack/` (procurement bundle + buyer evidence)
- `report/enterprise_eval/index.md` (evaluation index for reviewers)

Execution remains customer-managed; this path is assessment-first and non-mutating.

The generated procurement pack includes these review docs:

- `report/procurement_pack/docs/SECURITY_POSTURE.md`
- `report/procurement_pack/docs/SECURITY_QA.md`
- `report/procurement_pack/docs/COMPLIANCE_MATRIX.md`
- `report/procurement_pack/docs/WORKFLOW.md`
- `report/procurement_pack/docs/RELEASE.md`
- `report/procurement_pack/docs/DISTRIBUTION_POLICY.md`

## Review Links

- Repository overview: `README.md`
- Quickstart: `docs/QUICKSTART.md`
- Security posture: `docs/SECURITY_POSTURE.md`
- Buyer proof pack: `docs/BUYER_PROOF_PACK.md`
- Procurement pack: `docs/PROCUREMENT_PACK.md`
- Workflow details: `docs/WORKFLOW.md`
- Release process: `docs/RELEASE.md`
- Distribution policy: `docs/DISTRIBUTION_POLICY.md`
