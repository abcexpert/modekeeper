# ModeKeeper

[![CI](https://github.com/abcexpert/modekeeper/actions/workflows/ci.yml/badge.svg)](https://github.com/abcexpert/modekeeper/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/modekeeper.svg)](https://pypi.org/project/modekeeper/)

ModeKeeper is a verify-first operations agent for SRE, MLOps, and FinOps teams. The public runtime is customer-safe and read-only by default; apply is licensed and hard-gated.

## Contact
Documentation index: [`docs/INDEX.md`](docs/INDEX.md)


- Questions / feedback: GitHub Issues (preferred) and Discussions.
- Security issues: please use GitHub Security Advisories (private disclosure). See `.github/SECURITY.md`.

## Start here

- Buyer journey: [`docs/BUYER_JOURNEY.md`](docs/BUYER_JOURNEY.md)
- Product overview: [`docs/product.md`](docs/product.md)
- Quickstart: [`docs/QUICKSTART.md`](docs/QUICKSTART.md)
- Security posture: [`docs/SECURITY_POSTURE.md`](docs/SECURITY_POSTURE.md)
- Buyer proof pack: [`docs/BUYER_PROOF_PACK.md`](docs/BUYER_PROOF_PACK.md)
- Procurement pack: [`docs/PROCUREMENT_PACK.md`](docs/PROCUREMENT_PACK.md)
- Enterprise evaluation: [`docs/ENTERPRISE_EVALUATION.md`](docs/ENTERPRISE_EVALUATION.md)
- Current project status: [`docs/STATUS.md`](docs/STATUS.md)
- Workflow details: [`docs/WORKFLOW.md`](docs/WORKFLOW.md)
- Distribution boundary policy: [`docs/DISTRIBUTION_POLICY.md`](docs/DISTRIBUTION_POLICY.md)

## 60-second quickstart

```bash
python3 -m pip install -U modekeeper
mk doctor
mk quickstart --out report/quickstart

# quickstart artifacts
ls report/quickstart
ls report/quickstart/plan
ls report/quickstart/verify
ls report/quickstart/export
```

Expected artifact roots:
- `report/quickstart/plan` (dry-run planning outputs)
- `report/quickstart/verify` (verify report with `verify_ok`)
- `report/quickstart/export` (bundle/export outputs)

## Safety gates

Apply/mutate paths are blocked unless all required gates pass:
- `verify_ok=true` from verify artifacts
- kill-switch is absolute (`MODEKEEPER_KILL_SWITCH=1` blocks apply)
- valid license and apply entitlement

Details and command contracts:
- [`docs/QUICKSTART.md`](docs/QUICKSTART.md)
- [`docs/WORKFLOW.md`](docs/WORKFLOW.md)

## Public vs Pro

Public GitHub + PyPI (`modekeeper`) is the showroom/stub surface with verify-first workflows (`observe -> plan -> verify -> ROI -> export`). Apply/mutate capabilities are disabled by default in public and reserved for licensed distribution; see boundary and release rules in [`docs/DISTRIBUTION_POLICY.md`](docs/DISTRIBUTION_POLICY.md).
