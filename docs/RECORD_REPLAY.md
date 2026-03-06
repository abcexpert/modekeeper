# Record/Replay Playbook (Public)

Public reproducibility workflow: capture a short observe stream once, then replay from file for deterministic, verify-first iteration.

## 1) Record from Kubernetes

Capture a short observe trace from your own workload:

```bash
mk observe --source k8s \
  --k8s-namespace <ns> \
  --k8s-deployment <deployment> \
  --container <container> \
  --duration 30s \
  --out report/observe_capture
```

To persist raw input for later replay, add:

```bash
--record-raw /path/to/observe.jsonl
```

Record outputs are written under `report/observe_capture/`.

## 2) Replay from file (no live cluster required)

Replay the recorded JSONL in dry-run mode:

```bash
mk closed-loop run --scenario drift --dry-run \
  --observe-source file \
  --observe-path /path/to/observe.jsonl \
  --out report/replay_run
```

For multi-iteration playback:

```bash
mk closed-loop watch --scenario drift --dry-run \
  --observe-source file \
  --observe-path /path/to/observe.jsonl \
  --max-iterations 3 --interval 0s \
  --out report/replay_watch
```

## 3) Reproducibility checklist

- Keep source JSONL under versioned evidence folders in your own environment.
- Run with fixed input files and isolated output folders.
- Compare `*_latest.json`, `summary.md`, and `explain.jsonl` across runs.
- Prefer dry-run/verify-first commands when preparing enterprise review artifacts.

## 4) Notes

- Record once from Kubernetes, then iterate locally from file replay.
- This workflow exercises policy/planning/reporting paths without requiring continuous cluster access.
- Replay tolerates dirty logs (blank lines, invalid JSON, unexpected shapes, missing fields) by dropping bad entries instead of failing the run.
- Drop counters are exposed via `observe_ingest` in closed-loop reports.
