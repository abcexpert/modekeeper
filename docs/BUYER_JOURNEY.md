# Buyer Journey (Public Showroom)

This flow is for buyer-safe evaluation in public mode: install, validate environment, run verify-first workflows, and prepare procurement evidence without mutations.

## 1) Install

```bash
python3 -m pip install -U modekeeper
mk --version
```

## 2) Environment doctor

```bash
mk doctor
```

Expected: doctor exits with `0`.

## 3) Quickstart (safe default)

```bash
mk quickstart --out report/quickstart
```

## 4) Dry-run / plan / verify (no apply)

```bash
mk closed-loop run --scenario drift --dry-run --out report/buyer/plan
PLAN="$(python3 -c 'import json; print(json.load(open("report/buyer/plan/closed_loop_latest.json", encoding="utf-8"))["k8s_plan_path"])')"
mk k8s verify --plan "$PLAN" --out report/buyer/verify
mk estimate --in report/buyer/plan --out report/buyer/roi
mk export bundle --in report/buyer --out report/buyer/export
```

## 5) Procurement pack

```bash
./bin/mk-procurement-pack
```

Primary output: `report/procurement_pack/`.

## 6) Security and procurement notes

- Security posture: [SECURITY_POSTURE.md](SECURITY_POSTURE.md)
- Security Q&A: [SECURITY_QA.md](SECURITY_QA.md)
- Procurement pack guide: [PROCUREMENT_PACK.md](PROCUREMENT_PACK.md)
- Distribution boundary: [DISTRIBUTION_POLICY.md](DISTRIBUTION_POLICY.md)

## 7) Contact

- Product and procurement questions: GitHub Issues/Discussions.
- Security disclosures: GitHub Security Advisories (`.github/SECURITY.md`).
