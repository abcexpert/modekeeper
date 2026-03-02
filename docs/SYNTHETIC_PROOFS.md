# Synthetic Proof Pack v1 (File Replay)

This pack proves deterministic, buyer-safe behavior using replayed telemetry
from local files.

## What It Proves

- Single-signal behavior:
  - `burst=true` on bursty latency traces.
  - `straggler=true` on worker-latency outlier traces.
- Multi-signal behavior:
  - `drift=true` + `burst=true` in one run on combo traces.
- Deterministic replay:
  - Same input files produce the same class of signals and dry-run planning
    outputs.
- Read-only operation:
  - Observe + closed-loop dry-run only; no apply/mutate path is used.

## How To Run Locally

```bash
./scripts/e2e-synthetic-proofs-replay.sh
```

Output root:

- `out/synthetic_proofs/<UTC_TS>Z/`

Each scenario directory contains transcript, plan/observe artifacts,
summaries, metrics, sparklines, and SHA256 checksums.

## Scenarios And Expected Outcomes

- `stable`: `tests/data/observe/stable.jsonl`
  - Expected: no actionable signals.
- `burst`: `tests/data/observe/bursty.jsonl`
  - Expected: `signals.burst=true`.
- `dirty`: `tests/data/observe/realistic_dirty.jsonl`
  - Expected: `observe_ingest.dropped_total > 0` (ingest robustness on dirty input).
- `straggler`: `tests/data/observe/worker_latencies.jsonl`
  - Expected: `signals.straggler=true` and `TIMEOUT-GUARD` proposes `timeout_ms`.
- `combo`: `docs/evidence/mk060/observe_raw.jsonl`
  - Expected: `signals.drift=true` and `signals.burst=true`.

## Safety Scope

This proof pack is explicitly observe + closed-loop dry-run only (no apply).
