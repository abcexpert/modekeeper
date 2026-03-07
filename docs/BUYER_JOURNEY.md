# Buyer Journey (Public Read-Only Assessment)

This flow is for buyer-safe evaluation in public mode: install, validate environment, run verify-first workflows, and prepare procurement evidence without mutations.
Execution is customer-managed.

## 1) Install

```bash
python3 -m pip install -U modekeeper
mk --help
```

## 2) CLI availability check

```bash
mk --help
mk observe --help
mk closed-loop --help
mk roi --help
```

Expected: all help commands exit with `0`.

## 3) Observe (safe default)

```bash
mk observe --source synthetic --duration 30s --record-raw report/buyer/observe/observe_raw.jsonl --out report/buyer/observe
```

## 4) Plan / verify / export (+ optional ROI, no apply)

```bash
mk closed-loop run --scenario drift --dry-run --out report/buyer/plan
PLAN="$(python3 -c 'import json; print(json.load(open("report/buyer/plan/closed_loop_latest.json", encoding="utf-8"))["k8s_plan_path"])')"
mk k8s verify --plan "$PLAN" --out report/buyer/verify
mk export handoff-pack --in report/buyer --out report/buyer/handoff
# Optional supporting evidence:
mk roi estimate --observe-source file --observe-path report/buyer/observe/observe_raw.jsonl --out report/buyer/roi
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

## 8) External realistic workload proof (credibility input)

- Public summary: [ONLINE_BOUTIQUE_PROOF.md](ONLINE_BOUTIQUE_PROOF.md)
- Reproducible forced-scenario runbook: [ONLINE_BOUTIQUE_FORCED_OPPORTUNITIES.md](ONLINE_BOUTIQUE_FORCED_OPPORTUNITIES.md)

Scope note: this confirms a non-zero read-only signal/proposal path on two forced scenarios; it is not universal production coverage.
