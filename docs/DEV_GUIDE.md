# ModeKeeper Developer Guide

## 1) Local setup

### Prerequisites
- Python `>=3.10`
- `pip`
- `kubectl` (for k8s/preflight/verify scenarios)

### Recommended bootstrap
```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -U pip
python -m pip install -e .[dev]
```

### Quick sanity
```bash
mk --version
mk --help
mk doctor
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

## 3) Developer command flow

```bash
mk observe --source file --path tests/data/observe/stable.jsonl --duration 2s --out report/_observe
mk eval file --path tests/data/observe/stable.jsonl --out report/_eval
mk closed-loop run --scenario drift --dry-run --out report/_cl
mk k8s verify --plan report/_cl/k8s_plan.json --out report/_verify
mk export bundle --in report --out report/_bundle
```

## 4) Procurement pack build

Canonical command:
```bash
./bin/mk-procurement-pack
```

Output root:
- `report/procurement_pack/`

Main outputs:
- `report/procurement_pack/procurement_pack.tar.gz`
- `report/procurement_pack/checksums.sha256`
- `report/procurement_pack/buyer_pack/*`
- `report/procurement_pack/docs/*`
- `report/procurement_pack/meta/versions.txt`
- `report/procurement_pack/meta/pip_freeze.txt`

Checksum verification:
```bash
cd report/procurement_pack
sha256sum -c checksums.sha256
```

## 5) Important environment variables

### Core CLI runtime
- `KUBECTL`: path to kubectl binary used by k8s source/verify/apply checks.
- `KUBECONFIG`: kubeconfig path (doctor/preflight use it).
- `MODEKEEPER_KILL_SWITCH`: if `1`, apply/mutate paths are blocked.
- `MODEKEEPER_LICENSE_PATH`: license lookup fallback for apply/license verify.
- `MODEKEEPER_LICENSE_PUBLIC_KEYS_PATH`: keyring path override.

### Value model tuning
- `MODEKEEPER_GPU_HOUR_USD`
- `MODEKEEPER_GPU_COUNT`

### Installer/tooling (`bin/mk-install`)
- `MODEKEEPER_REPO_BASE_URL`
- `MODEKEEPER_WHEEL`
- `MODEKEEPER_LICENSE_GATE_URL`
- `MODEKEEPER_PRO_WHEEL_URL`
- `MODEKEEPER_LICENSE`

### Trainer runtime
- `MODEKEEPER_POD_NAME`, `MODEKEEPER_POD_NAMESPACE`
- `MODEKEEPER_SA_NAMESPACE_FILE`, `MODEKEEPER_SA_TOKEN_FILE`, `MODEKEEPER_SA_CA_FILE`
- `MODEKEEPER_API_TIMEOUT_S`, `MODEKEEPER_LOOP_INTERVAL_S`
- `MODEKEEPER_ANNOTATIONS_FILE`

### Internal/dev override path (for tests/integration)
- `MODEKEEPER_INTERNAL_OVERRIDE`
- `MODEKEEPER_PAID`

## 6) Troubleshooting baseline
- `mk doctor` should pass before k8s-oriented tests.
- Use isolated output dirs (`report/_...`) for deterministic local runs.
- If k8s verify fails, inspect `explain.jsonl` first, then `*_latest.json`.
