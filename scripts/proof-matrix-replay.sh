#!/usr/bin/env bash
set -Eeuo pipefail

on_err() {
  local rc=$?
  local line_no="${BASH_LINENO[0]:-unknown}"
  echo "[error] ${BASH_SOURCE[1]}:${line_no} exited with status ${rc}" >&2
}
trap on_err ERR

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

usage() {
  cat <<'EOF'
Usage: scripts/proof-matrix-replay.sh [--out DIR]

Runs the post-v0.1.33 proof scenarios in one deterministic flow and writes:
  - <out>/proof_matrix.json
  - <out>/proof_matrix.md
  - <out>/<scenario>/closed_loop artifacts for each scenario
EOF
}

OUT_ROOT=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --out)
      OUT_ROOT="${2:-}"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [[ -z "${OUT_ROOT}" ]]; then
  UTC_TS="$(date -u +%Y%m%dT%H%M%S)"
  OUT_ROOT="out/proof_matrix/${UTC_TS}Z"
fi
mkdir -p "${OUT_ROOT}"

if [[ -n "${MK_BIN:-}" ]]; then
  if [[ ! -x "${MK_BIN}" ]]; then
    echo "MK_BIN is set but not executable: ${MK_BIN}" >&2
    exit 1
  fi
elif [[ -x "./.venv/bin/mk" ]]; then
  MK_BIN="./.venv/bin/mk"
elif [[ -x "${HOME}/.modekeeper/venv/bin/mk" ]]; then
  MK_BIN="${HOME}/.modekeeper/venv/bin/mk"
else
  echo "mk binary not found. Set MK_BIN or run ./bin/mk-install and retry." >&2
  exit 1
fi

SCENARIOS=("replica_overprovisioning" "cpu_pressure" "memory_pressure")
for scenario in "${SCENARIOS[@]}"; do
  scenario_dir="${OUT_ROOT}/${scenario}"
  mkdir -p "${scenario_dir}"
  "${MK_BIN}" closed-loop run --scenario "${scenario}" --dry-run --out "${scenario_dir}"
done

python3 - "${OUT_ROOT}" "${ROOT_DIR}" <<'PY'
import json
import sys
from pathlib import Path

out_root = Path(sys.argv[1])
root_dir = Path(sys.argv[2])
sys.path.insert(0, (root_dir / "src").as_posix())

from modekeeper._proof_matrix_expectations import PROOF_MATRIX_EXPECTATIONS, PROOF_SCENARIO_ORDER

rows = []
for scenario in PROOF_SCENARIO_ORDER:
    scenario_dir = out_root / scenario
    latest = json.loads((scenario_dir / "closed_loop_latest.json").read_text(encoding="utf-8"))
    trace_lines = (scenario_dir / "decision_trace_latest.jsonl").read_text(encoding="utf-8").splitlines()
    first_trace = json.loads(trace_lines[0]) if trace_lines else {}
    signals = first_trace.get("signals", {})
    notes = signals.get("notes", []) if isinstance(signals, dict) else []
    action_knobs = {
        action.get("knob")
        for action in first_trace.get("actions", [])
        if isinstance(action, dict) and action.get("knob")
    }

    expected = PROOF_MATRIX_EXPECTATIONS[scenario]
    checks = {
        "assessment_signal_found": latest.get("assessment_result_class") == "signal_found",
        "coverage_ok": latest.get("coverage_ok") is True,
        "insufficient_evidence_empty": latest.get("insufficient_evidence_reasons") == [],
        "signal_count_positive": latest.get("signal_count", 0) > 0,
        "actionable_proposals_positive": latest.get("actionable_proposal_count", 0) > 0,
        "k8s_plan_items_positive": latest.get("k8s_plan_items", 0) > 0,
        "signal_flags_match": all(signals.get(k) is v for k, v in expected["signal_flags"].items()),
        "expected_note_present": expected["note"] in notes,
        "action_knobs_match": action_knobs == expected["knobs"],
    }
    passed = all(checks.values())
    failures = [name for name, ok in checks.items() if not ok]

    rows.append(
        {
            "scenario": scenario,
            "passed": passed,
            "failed_checks": failures,
            "assessment_result_class": latest.get("assessment_result_class"),
            "signal_count": latest.get("signal_count"),
            "actionable_proposal_count": latest.get("actionable_proposal_count"),
            "k8s_plan_items": latest.get("k8s_plan_items"),
            "signals": {k: signals.get(k) for k in ("drift", "burst", "straggler", "noise")},
            "notes": notes,
            "action_knobs": sorted(action_knobs),
            "out_dir": scenario_dir.as_posix(),
        }
    )

passed_count = sum(1 for row in rows if row["passed"])
matrix = {
    "schema_version": "v1_internal",
    "harness": "proof_matrix_replay",
    "scenario_order": [row["scenario"] for row in rows],
    "passed_count": passed_count,
    "failed_count": len(rows) - passed_count,
    "all_passed": passed_count == len(rows),
    "rows": rows,
}

matrix_json = out_root / "proof_matrix.json"
matrix_json.write_text(json.dumps(matrix, indent=2, sort_keys=True) + "\n", encoding="utf-8")

md_lines = [
    "# Proof Matrix Replay",
    "",
    f"- all_passed: {str(matrix['all_passed']).lower()}",
    f"- passed_count: {matrix['passed_count']}",
    f"- failed_count: {matrix['failed_count']}",
    "",
    "| scenario | pass | class | signals(drift,burst) | proposals | plan_items |",
    "| --- | --- | --- | --- | --- | --- |",
]
for row in rows:
    md_lines.append(
        "| {scenario} | {passed} | {klass} | ({drift},{burst}) | {proposals} | {items} |".format(
            scenario=row["scenario"],
            passed="PASS" if row["passed"] else "FAIL",
            klass=row["assessment_result_class"],
            drift=row["signals"]["drift"],
            burst=row["signals"]["burst"],
            proposals=row["actionable_proposal_count"],
            items=row["k8s_plan_items"],
        )
    )
    if row["failed_checks"]:
        md_lines.append(f"| {row['scenario']} failures | {', '.join(row['failed_checks'])} | | | | |")

(out_root / "proof_matrix.md").write_text("\n".join(md_lines) + "\n", encoding="utf-8")

if not matrix["all_passed"]:
    raise SystemExit(1)
PY

echo "proof-matrix replay complete: ${OUT_ROOT}"
