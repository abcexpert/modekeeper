# HANDOFF

## See also
- `docs/SNAPSHOT.md` - current product state and canonical execution model.
- `docs/K8S_RUNNER_SELF_SERVE.md` - customer-managed runner lifecycle.
- `docs/DISTRIBUTION_POLICY.md` - public vs licensed distribution boundary.
- `docs/RELEASING.md` - release boundary and packaging context.

## Buyer-facing summary
ModeKeeper is a verify-first, read-only assessment product for Kubernetes/GPU cost and risk.
Default public workflows are strict read-only assessment (`observe -> plan -> verify -> export`) for safe evaluation without cluster mutation.
Execution is customer-managed. Licensed apply/implementation is a separate gated path and is not part of baseline public handoff execution.

## What the customer receives
A standard handoff pack is built as deterministic artifacts that can be transferred, validated, and reviewed by the customer team:

- `handoff_pack.tar.gz`
- `handoff_manifest.json`
- `handoff_summary.md`
- `handoff_pack.checksums.sha256`
- `HANDOFF_VERIFY.sh`
- `README.md`

This package is designed for security/procurement review and operational continuity:
- integrity-first review (hash verification before content review),
- reproducible evidence trail,
- portable archive for internal sharing and audit.

## Change-ready handoff pack
The handoff is "change-ready" because it includes both context and verification material needed to continue safely:

- run outputs from customer-managed execution,
- manifest-level inventory of delivered files,
- checksum manifest for tamper detection,
- one-command verification script (`HANDOFF_VERIFY.sh`),
- concise summary for quick buyer/operator triage.

The result is a package that supports controlled continuation of evaluation and change planning without requiring vendor-operated runtime access.

## Customer-managed flow (canonical)
1. Run customer-managed read-only quickstart in the runner environment.
2. Copy artifacts from runner output to customer-controlled storage.
3. Build handoff package locally:

```bash
mk export handoff-pack --in ./out/quickstart --out ./handoff
```

4. Verify package integrity before review:

```bash
cd ./handoff
bash HANDOFF_VERIFY.sh
```

Success criterion: verification prints `OK`.

Operational note:
- `top_blocker=rbac_denied` in read-only verify artifacts is a non-blocking note for this handoff flow and does not prevent handoff-pack verification.

## Checksums and verification policy
Handoff acceptance starts from integrity checks, not from narrative review.

Minimum verification policy:
- run `HANDOFF_VERIFY.sh` on receipt,
- ensure checksum validation passes,
- review `handoff_manifest.json` and `handoff_summary.md` only after successful integrity check,
- archive both pack and verification output in customer-controlled storage.

This keeps evidence handling deterministic and audit-friendly.

## Public vs PRO boundary (high-level)
Public surface:
- verify-first read-only workflows,
- buyer-safe evaluation and evidence export,
- no default mutation path in standard public handoff.

Licensed PRO surface:
- gated mutate/apply capabilities,
- additional commercial controls and entitlements,
- still enforced by safety gates (including verification and kill-switch semantics).

Boundary principle:
- customer handoff materials must remain safe to share in public channels,
- sensitive internal operator/release infrastructure details are excluded from this document.

## Scope of this document
This `HANDOFF.md` is intentionally customer-facing.
It describes what is delivered, how it is verified, and how to continue in customer-managed mode.
Internal operator procedures, private infrastructure layout, and internal roadmap content are out of scope.
