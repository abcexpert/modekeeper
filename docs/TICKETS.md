# Tickets (Public)

This file is the public-facing roadmap/status ledger for ModeKeeper's verify-first, read-only assessment surface.

## Public boundary for this ledger
- Keep customer-safe, verify-first roadmap items only.
- Keep customer-managed execution scope (customer runs observe/plan/verify/export in their environment).
- Keep enterprise review and handoff-pack outcomes that can be shared publicly.
- Exclude internal operator workflows, private infrastructure paths, private repository choreography, and internal-only licensing/release mechanics.

## Status values
- `TODO` - planned public-facing work.
- `DONE` - shipped and reflected in public docs/CLI surface.

- EPIC: Customer-managed verify-first assessment and handoff
  Goal:
    - Maintain a strict read-only evaluation path (`observe -> plan -> verify -> export`) and clear handoff evidence for enterprise review.

- ID: MK-130
  Title: mk doctor (public-safe environment/readiness checks + actionable output)
  Status: TODO
  Acceptance criteria:
    - `mk doctor` validates local prerequisites and access visibility in one command.
    - Output is actionable and customer-safe (read-only, no cluster mutation).
    - Terminal summary and machine-readable artifact remain deterministic.
  Public evidence stub:
    - docs:
    - artifacts:
    - tests:
    - commit:

- ID: MK-131
  Title: mk support-bundle (sanitized support pack for customer-controlled sharing)
  Status: TODO
  Acceptance criteria:
    - `mk support-bundle` creates a reproducible support pack with explicit redaction behavior.
    - Bundle includes a manifest with included files and generation metadata.
    - Pack is safe for customer-managed escalation and enterprise review.
  Public evidence stub:
    - docs:
    - artifacts:
    - tests:
    - commit:

- ID: MK-132
  Title: mk export handoff-pack (deterministic archive + checksum + verify transcript)
  Status: TODO
  Acceptance criteria:
    - `mk export handoff-pack` emits archive and integrity artifacts that can be verified offline.
    - Verification flow is explicit pass/fail and records transcript evidence.
    - Export is deterministic for identical inputs and does not require vendor runtime access.
  Public evidence stub:
    - docs:
    - artifacts:
    - tests:
    - commit:

- ID: MK-133
  Title: mk install k8s-runner (customer-owned manifests for runner execution)
  Status: DONE
  Public outcome:
    - Customer-manageable runner manifests are generated and reviewable before apply.
    - Public runbook flow remains customer-owned and verify-first.
  Public evidence:
    - docs: `docs/K8S_RUNNER_SELF_SERVE.md`
    - references: `docs/HANDOFF.md`, `docs/SNAPSHOT.md`

- ID: MK-134
  Title: Customer-managed runbook lifecycle (install/upgrade/rollback/uninstall + offline notes)
  Status: DONE
  Public outcome:
    - A single customer-facing lifecycle runbook exists for customer-managed operation.
    - Offline/air-gapped handling is documented at public guidance level.
  Public evidence:
    - docs: `docs/K8S_RUNNER_SELF_SERVE.md`, `docs/INDEX.md`, `docs/README.md`

- ID: MK-135
  Title: Docs alignment for customer-managed execution boundary
  Status: DONE
  Public outcome:
    - Public docs consistently describe verify-first read-only evaluation and gated apply boundary.
    - Handoff/releasing/snapshot wording is aligned for enterprise reviewers.
  Public evidence:
    - docs: `docs/HANDOFF.md`, `docs/RELEASE.md`, `docs/SNAPSHOT.md`

- ID: MK-136
  Title: Enterprise review pack hardening (procurement/security handoff clarity)
  Status: TODO
  Acceptance criteria:
    - Public guidance for integrity-first review order is clear and consistent across buyer/procurement docs.
    - Required evidence set for security/procurement review is explicit and reproducible.
  Public evidence stub:
    - docs: `docs/OFFER.md`, `docs/ICP.md`, `docs/BUYER_REQUEST_CHECKLIST.md`
    - artifacts:
    - commit:

- ID: MK-137
  Title: Public status hygiene (keep roadmap/status/evidence links current)
  Status: TODO
  Acceptance criteria:
    - `docs/TICKETS.md`, `docs/STATUS.md`, and public roadmap references stay mutually consistent.
    - Stale references to removed/internal docs are not reintroduced.
  Public evidence stub:
    - docs: `docs/INDEX.md`, `docs/SNAPSHOT.md`, `docs/STATUS.md`
    - artifacts:
    - commit:

- ID: MK-138
  Title: Observable pattern detection quality + insufficient-evidence classification + forced-opportunity proofs
  Status: DONE
  Public outcome:
    - Public Pattern Catalog and Observability Contract define outcome classes and insufficient-evidence handling for verify-first read-only assessment.
    - Forced-opportunity scenarios are documented, and an Online Boutique external proof summary records non-zero read-only signal/proposal outcomes for forced oversized-request and burst-traffic scenarios.
  Public evidence:
    - docs: `docs/PATTERN_CATALOG.md`, `docs/OBSERVABILITY_CONTRACT.md`, `docs/FORCED_OPPORTUNITY_SCENARIOS.md`, `docs/ONLINE_BOUTIQUE_FORCED_OPPORTUNITIES.md`, `docs/ONLINE_BOUTIQUE_PROOF.md`
