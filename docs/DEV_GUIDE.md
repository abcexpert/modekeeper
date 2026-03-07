# ModeKeeper Developer Guide (Public)

Public contributor guide for local development, testing, and verify-first evaluation flows.

## 1) Local setup

### Prerequisites
- Python `>=3.10`
- `pip`
- `kubectl` (for Kubernetes preflight/verify scenarios)

### Recommended bootstrap
```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install -e .[dev]
```

### Quick sanity
```bash
mk --help
mk observe --help
mk closed-loop --help
```

## 2) Running tests

### Full suite
```bash
pytest -q
```

### Targeted suites
```bash
pytest -q tests/test_cli_artifacts.py
pytest -q tests/test_k8s_verify.py
pytest -q tests/test_report_contracts.py
```

## 3) Verify-first developer flow

Use read-only and dry-run commands first, with isolated output folders for deterministic local runs.

```bash
mk observe --source file --path tests/data/observe/stable.jsonl --duration 2s --out report/_observe
mk eval file --path tests/data/observe/stable.jsonl --out report/_eval
mk closed-loop run --scenario drift --dry-run --out report/_cl
mk k8s verify --plan report/_cl/k8s_plan.json --out report/_verify
mk export bundle --in report --out report/_bundle
```

## 4) Public handoff-pack direction

For customer-managed evaluation handoff, build and verify a handoff pack locally:

```bash
mk export handoff-pack --in report --out report/_handoff
```

Then validate checksums and include generated artifacts in the review package shared with procurement/security stakeholders.

## 5) Environment variables (public-safe)

### Core CLI runtime
- `KUBECTL`: path to the `kubectl` binary used by Kubernetes commands.
- `KUBECONFIG`: kubeconfig path for cluster access.
- `MODEKEEPER_KILL_SWITCH`: if `1`, blocks mutating apply paths.

### Value model tuning
- `MODEKEEPER_GPU_HOUR_USD`
- `MODEKEEPER_GPU_COUNT`

## 6) Troubleshooting baseline
- `mk k8s preflight --help` and `mk k8s verify --help` should work before Kubernetes-oriented tests.
- Use isolated output dirs (`report/_...`) for reproducible runs.
- If `mk k8s verify` fails, inspect `explain.jsonl` first, then `*_latest.json`.
