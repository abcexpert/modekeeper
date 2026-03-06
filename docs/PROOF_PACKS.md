# Proof Packs

This page summarizes the public proof-pack workflows in one place.

Start here: [BUYER_10MIN.md](BUYER_10MIN.md)

## Public Scenarios

### 1) Buyer pack

Run:

```bash
./bin/mk-buyer-pack
```

Output on disk:

- `report/buyer_pack/plan/`
- `report/buyer_pack/verify/`
- `report/buyer_pack/dryrun/`
- `report/buyer_pack/export/`
- `report/buyer_pack/summary.md`

Key artifacts to inspect:

- `report/buyer_pack/plan/closed_loop_latest.json` (`verify_ok`, license/apply gate summary)
- `report/buyer_pack/verify/k8s_verify_latest.json` (`ok`, `verify_blocker`)
- `report/buyer_pack/dryrun/k8s_plan.json` (non-mutating rendered plan)
- `report/buyer_pack/dryrun/closed_loop_latest.json` (dry-run decision summary)

Verify (when a `checksums.sha256` manifest is included with the handoff):

```bash
cd report/buyer_pack && sha256sum -c checksums.sha256
```

### External realistic workload proof (Online Boutique)

Public summary:
- `docs/ONLINE_BOUTIQUE_PROOF.md`

Local artifacts (customer-managed, not committed to git):
- `report/online_boutique/BUYER_PROOF_INDEX.md`
- `report/online_boutique/forced_oversized/**`
- `report/online_boutique/forced_burst/**`

### 2) Procurement pack

Run:

```bash
./bin/mk-procurement-pack
```

Output on disk:

- `report/procurement_pack/procurement_pack.tar.gz`
- `report/procurement_pack/checksums.sha256`
- `report/procurement_pack/buyer_pack/**`
- `report/procurement_pack/docs/**`
- `report/procurement_pack/meta/**`

Key artifacts to inspect:

- `report/procurement_pack/buyer_pack/plan/closed_loop_latest.json`
- `report/procurement_pack/buyer_pack/verify/k8s_verify_latest.json`
- `report/procurement_pack/buyer_pack/dryrun/k8s_plan.json`
- `report/procurement_pack/docs/SECURITY_POSTURE.md`
- `report/procurement_pack/docs/SECURITY_QA.md`
- `report/procurement_pack/docs/COMPLIANCE_MATRIX.md`

Verify:

```bash
cd report/procurement_pack && sha256sum -c checksums.sha256
```

### 3) Enterprise eval

Run:

```bash
./bin/mk-enterprise-eval
```

Output on disk:

- `report/enterprise_eval/index.md`
- `report/procurement_pack/procurement_pack.tar.gz`
- `report/procurement_pack/checksums.sha256`
- `report/procurement_pack/buyer_pack/**`

Key artifacts to inspect:

- `report/enterprise_eval/index.md` (review index)
- `report/procurement_pack/buyer_pack/plan/closed_loop_latest.json`
- `report/procurement_pack/buyer_pack/verify/k8s_verify_latest.json`
- `report/procurement_pack/buyer_pack/dryrun/closed_loop_latest.json`

Verify:

```bash
cd report/procurement_pack && sha256sum -c checksums.sha256
```

## PRO (private) vault-only deliverables

Private/proprietary delivery is handled outside public repo artifacts:

- GitHub Releases are notes-only (no binary assets attached).
- Deliverables are distributed via vault stamps on authorized hosts.
- Verification is done from delivery transcripts plus SHA256 checks.
