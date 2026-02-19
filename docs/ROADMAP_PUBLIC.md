# ModeKeeper Public Roadmap

## What ModeKeeper is
ModeKeeper is a verify-first operations agent for SRE/MLOps/FinOps workflows. In the public showroom, workflows are intentionally read-only (`observe -> dry-run plan -> verify -> ROI -> export`) so teams can evaluate safety, controls, and value evidence without cluster mutation. Licensed apply is a separate gated path (`--apply`) that only proceeds when verification passes, kill-switch is not active, and license entitlements allow mutation.

References: `README.md`, `docs/WORKFLOW.md`, `docs/DISTRIBUTION_POLICY.md`, `docs/QUICKSTART.md`.

## Shipped today (public + buyer/procurement flow)
- Verify-first read-only workflow and artifacts:
  - `mk quickstart --out report/quickstart`
  - Key outputs: `report/quickstart/plan/closed_loop_latest.json`, `report/quickstart/verify/k8s_verify_latest.json`, `report/quickstart/export/bundle_summary.md`
  - See `docs/QUICKSTART.md`, `docs/CLI_REFERENCE.md`.
- Deterministic bundle export for reviewer handoff:
  - `mk export bundle --in report/quickstart --out report/quickstart/export`
  - Outputs: `bundle_manifest.json`, `bundle.tar.gz`, `bundle_summary.md`
  - See `docs/CLI_REFERENCE.md`.
- Buyer evidence pack (customer-safe, read-only):
  - `./bin/mk-buyer-pack`
  - Outputs under `report/buyer_pack/**` (plan/verify/preflight/eval/watch/roi/export/dryrun)
  - See `docs/BUYER_PROOF_PACK.md`.
- Procurement/RFI pack with integrity artifacts:
  - `./bin/mk-procurement-pack`
  - Outputs: `report/procurement_pack/procurement_pack.tar.gz`, `report/procurement_pack/checksums.sha256`, `report/procurement_pack/buyer_pack/**`, `report/procurement_pack/docs/**`
  - See `docs/PROCUREMENT_PACK.md`.
- One-command enterprise evaluation index:
  - `./bin/mk-enterprise-eval`
  - Output: `report/enterprise_eval/index.md`
  - See `docs/ENTERPRISE_EVALUATION.md`.
- Licensed apply gates are implemented in CLI flow:
  - Commands: `mk license verify`, `mk k8s apply`, `mk closed-loop run --apply`
  - Gate signals in artifacts: `verify_ok`, `apply_blocked_reason`, `kill_switch_active`, `license_ok`
  - See `docs/WORKFLOW.md`, `docs/CLI_REFERENCE.md`, `docs/INTERNAL_LICENSE_ISSUANCE.md`.

## Enterprise commercial next (priority)
- License key management hardening: explicit `kid`, rotation workflow, verification allowlist, and optional trust chain mode for enterprise PKI interoperability.
- Absolute kill-switch operations at fleet scope: fail-closed behavior, out-of-band propagation, and tamper-evident audit trail for emergency mutation stop.
- License lifecycle controls: revocation/status checks, short-lived/renewable licenses, and reason-coded deny telemetry for SOC workflows.
- Identity + approvals: SSO-backed RBAC, dual-control approvals for apply, and immutable decision/audit logs mapped to reviewer identity.
- Apply safety depth: staged/canary apply with automatic rollback enforcement (beyond current rollback-plan references).
- Kubernetes coverage expansion: first-class support beyond deployment patches (broader object kinds and validators).
- Release provenance upgrades: signed release assets + SBOM/attestation packaged with procurement artifacts.
- Centralized policy/governance plane: multi-cluster policy propagation, drift detection, and control attestation at organization scope.

## How to evaluate (short path)
1. Download release assets (`procurement_pack.tar.gz` and `checksums.sha256`) from the GitHub Release for your target version (`docs/RELEASE.md`, `docs/RELEASE_PROCESS.md`).
2. Verify integrity:
   - `sha256sum -c checksums.sha256`
3. Unpack and inspect key evidence:
   - `buyer_pack/plan/closed_loop_latest.json`
   - `buyer_pack/verify/k8s_verify_latest.json`
   - `buyer_pack/export/bundle_summary.md`
4. Interpret decision signals in `bundle_summary.md`:
   - `roi.ok: true` means ROI pipeline checks passed for the exported input set.
   - `top_blocker: n/a` means no blocking condition was detected.
   - Any non-empty `top_blocker` is the first remediation target before apply discussions.

See also: `docs/BUYER_PROOF_PACK.md`, `docs/PROCUREMENT_PACK.md`, `docs/SECURITY_QA.md`.
