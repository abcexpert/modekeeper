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

if [[ -x "./.venv/bin/mk" ]]; then
  MK_BIN="./.venv/bin/mk"
elif [[ -x "${HOME}/.modekeeper/venv/bin/mk" ]]; then
  MK_BIN="${HOME}/.modekeeper/venv/bin/mk"
else
  echo "mk binary not found. Run ./bin/mk-install and retry." >&2
  exit 1
fi

UTC_TS="$(date -u +%Y%m%dT%H%M%S)"
OUT_ROOT="out/synthetic_proofs/${UTC_TS}Z"
mkdir -p "${OUT_ROOT}"

run_scenario() {
  local scenario="$1"
  local trace_path="$2"
  local scenario_dir="${OUT_ROOT}/${scenario}"
  local transcript="${scenario_dir}/TRANSCRIPT.txt"

  mkdir -p "${scenario_dir}"
  : > "${transcript}"

  run_and_log() {
    echo "\$ $*" | tee -a "${transcript}"
    "$@" 2>&1 | tee -a "${transcript}"
    local rc=${PIPESTATUS[0]}
    echo | tee -a "${transcript}"
    return "${rc}"
  }

  run_and_log "${MK_BIN}" observe --source file --path "${trace_path}" --duration 1s --out "${scenario_dir}/observe"
  run_and_log "${MK_BIN}" closed-loop run --scenario drift --dry-run --observe-source file --observe-path "${trace_path}" --out "${scenario_dir}/plan"

  echo "\$ python3 summarize+metrics ${scenario} ${trace_path}" | tee -a "${transcript}"
  python3 - "${scenario}" "${trace_path}" "${scenario_dir}" <<'PY' 2>&1 | tee -a "${transcript}"
import csv
import json
import math
import sys
from pathlib import Path

scenario = sys.argv[1]
trace_path = Path(sys.argv[2])
scenario_dir = Path(sys.argv[3])
plan_dir = scenario_dir / "plan"

closed_loop = json.loads((plan_dir / "closed_loop_latest.json").read_text(encoding="utf-8"))

trace_lines = (plan_dir / "decision_trace_latest.jsonl").read_text(encoding="utf-8").splitlines()
first_event = json.loads(trace_lines[0]) if trace_lines else {}
signals = first_event.get("signals") if isinstance(first_event.get("signals"), dict) else {}

active = []
for key, value in signals.items():
    if key == "notes":
        continue
    if value is True:
        active.append(key)
active.sort()
active_signals = ", ".join(active) if active else "(none)"

timeout_actions = []
for line in trace_lines:
    event = json.loads(line)
    actions = event.get("actions")
    if not isinstance(actions, list):
        continue
    for action in actions:
        if not isinstance(action, dict):
            continue
        if action.get("knob") == "timeout_ms":
            timeout_actions.append(action)

straggler_note = ""
if scenario == "straggler":
    guard = [a for a in timeout_actions if a.get("chord") == "TIMEOUT-GUARD"]
    if guard:
        targets = sorted({a.get("target") for a in guard if isinstance(a.get("target"), (int, float))})
        target_text = ", ".join(str(int(v)) if float(v).is_integer() else str(v) for v in targets)
        straggler_note = f"Expected straggler proof: TIMEOUT-GUARD proposes timeout_ms (targets: {target_text})."
    else:
        straggler_note = "Expected straggler proof missing: no TIMEOUT-GUARD timeout_ms action found."

observe_ingest = closed_loop.get("observe_ingest")
observe_ingest_lines = []
if isinstance(observe_ingest, dict):
    for key in sorted(observe_ingest):
        if key.startswith("dropped_"):
            observe_ingest_lines.append(f"- {key}: {observe_ingest[key]}")

summary_lines = [
    f"# Scenario: {scenario}",
    "",
    f"- trace: {trace_path.as_posix()}",
    f"- active_signals: {active_signals}",
    f"- k8s_plan_items: {closed_loop.get('k8s_plan_items')}",
]
if straggler_note:
    summary_lines.append(f"- note: {straggler_note}")
if observe_ingest_lines:
    summary_lines.append("- observe_ingest:")
    summary_lines.extend(observe_ingest_lines)

(scenario_dir / "summary.md").write_text("\n".join(summary_lines) + "\n", encoding="utf-8")

def p95(values):
    ordered = sorted(float(v) for v in values)
    if not ordered:
        return None
    if len(ordered) == 1:
        return ordered[0]
    pos = 0.95 * (len(ordered) - 1)
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return ordered[lo]
    frac = pos - lo
    return ordered[lo] * (1.0 - frac) + ordered[hi] * frac

rows = []
with trace_path.open("r", encoding="utf-8") as f:
    for idx, line in enumerate(f):
        line = line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(payload, dict):
            continue
        entry = {"idx": idx, "ts": payload.get("ts")}
        step = payload.get("step_time_ms")
        entry["step_time_ms"] = float(step) if isinstance(step, (int, float)) else None
        loss = payload.get("loss")
        entry["loss"] = float(loss) if isinstance(loss, (int, float)) else None
        worker = payload.get("worker_latencies_ms")
        if isinstance(worker, list):
            numeric = [v for v in worker if isinstance(v, (int, float))]
            entry["worker_lat_p95_ms"] = p95(numeric) if numeric else None
        else:
            entry["worker_lat_p95_ms"] = None
        rows.append(entry)

metrics_csv = scenario_dir / "metrics.csv"
with metrics_csv.open("w", encoding="utf-8", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["idx", "ts", "step_time_ms", "loss", "worker_lat_p95_ms"])
    for row in rows:
        writer.writerow(
            [
                row.get("idx"),
                row.get("ts", ""),
                "" if row.get("step_time_ms") is None else f"{row['step_time_ms']:.6f}",
                "" if row.get("loss") is None else f"{row['loss']:.6f}",
                "" if row.get("worker_lat_p95_ms") is None else f"{row['worker_lat_p95_ms']:.6f}",
            ]
        )

def sparkline(values):
    chars = " .:-=+*#%@"
    if not values:
        return "(no data)"
    lo = min(values)
    hi = max(values)
    if hi == lo:
        return chars[-1] * min(len(values), 64)
    out = []
    for val in values[:128]:
        norm = (val - lo) / (hi - lo)
        idx = int(round(norm * (len(chars) - 1)))
        out.append(chars[max(0, min(idx, len(chars) - 1))])
    return "".join(out)

series = {
    "step_time_ms": [r["step_time_ms"] for r in rows if r.get("step_time_ms") is not None],
    "loss": [r["loss"] for r in rows if r.get("loss") is not None],
    "worker_lat_p95_ms": [r["worker_lat_p95_ms"] for r in rows if r.get("worker_lat_p95_ms") is not None],
}

spark_lines = ["# Metrics Sparkline", ""]
for key, values in series.items():
    spark_lines.append(f"- {key}: {sparkline(values)}")
    if values:
        spark_lines.append(f"  n={len(values)} min={min(values):.6f} max={max(values):.6f}")
    else:
        spark_lines.append("  n=0")

(scenario_dir / "metrics.sparkline.md").write_text("\n".join(spark_lines) + "\n", encoding="utf-8")
print("summary, metrics.csv, and metrics.sparkline.md written")
PY
  local py_rc=${PIPESTATUS[0]}
  echo | tee -a "${transcript}"
  if [[ "${py_rc}" -ne 0 ]]; then
    return "${py_rc}"
  fi

  (
    cd "${scenario_dir}"
    find . -type f ! -name "sha256sums.txt" -print0 | sort -z | xargs -0 sha256sum > "sha256sums.txt"
  )
}

run_scenario "stable" "tests/data/observe/stable.jsonl"
run_scenario "burst" "tests/data/observe/bursty.jsonl"
run_scenario "dirty" "tests/data/observe/realistic_dirty.jsonl"
run_scenario "straggler" "tests/data/observe/worker_latencies.jsonl"
run_scenario "combo" "docs/evidence/mk060/observe_raw.jsonl"

echo "Synthetic proofs replay complete: ${OUT_ROOT}"
