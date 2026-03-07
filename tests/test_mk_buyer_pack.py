import os
import shutil
import subprocess
from pathlib import Path


def test_mk_buyer_pack_minimal_runtime_contract(tmp_path: Path) -> None:
    source_repo = Path(__file__).resolve().parents[1]
    source_script = source_repo / "bin" / "mk-buyer-pack"

    repo_root = tmp_path / "repo"
    (repo_root / "bin").mkdir(parents=True)
    script = repo_root / "bin" / "mk-buyer-pack"
    shutil.copy2(source_script, script)
    script.chmod(0o755)

    test_bin = tmp_path / "test-bin"
    test_bin.mkdir(parents=True)
    calls_log = tmp_path / "mk_calls.log"
    mk_stub = test_bin / "mk"
    mk_stub.write_text(
        """#!/usr/bin/env bash
set -Eeuo pipefail

printf '%s\\n' "$*" >> "${MK_CALLS_LOG:?}"

if [[ "${1:-}" == "doctor" ]]; then
  exit 0
fi

if [[ "${1:-}" == "quickstart" ]]; then
  OUT=""
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --out)
        OUT="$2"
        shift 2
        ;;
      *)
        shift
        ;;
    esac
  done
  mkdir -p "$OUT/plan" "$OUT/verify" "$OUT/preflight" "$OUT/eval" "$OUT/watch" "$OUT/roi" "$OUT/export"
  echo "{}" >"$OUT/plan/closed_loop_latest.json"
  echo '{"event":"plan"}' >"$OUT/plan/decision_trace_latest.jsonl"
  echo "{}" >"$OUT/verify/k8s_verify_latest.json"
  echo "{}" >"$OUT/preflight/preflight_latest.json"
  echo "# preflight" >"$OUT/preflight/summary.md"
  echo "{}" >"$OUT/eval/eval_latest.json"
  echo "# eval" >"$OUT/eval/summary.md"
  echo "{}" >"$OUT/watch/watch_latest.json"
  echo "# watch" >"$OUT/watch/summary.md"
  echo "{}" >"$OUT/roi/roi_latest.json"
  echo "# roi" >"$OUT/roi/summary.md"
  echo "{}" >"$OUT/export/bundle_manifest.json"
  echo "stub bundle tarball" >"$OUT/export/bundle.tar.gz"
  exit 0
fi

if [[ "${1:-}" == "closed-loop" ]] && [[ "${2:-}" == "run" ]]; then
  OUT=""
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --out)
        OUT="$2"
        shift 2
        ;;
      *)
        shift
        ;;
    esac
  done
  mkdir -p "$OUT"
  echo "{}" >"$OUT/closed_loop_latest.json"
  echo "{}" >"$OUT/k8s_plan.json"
  echo '{"event":"dryrun"}' >"$OUT/decision_trace_latest.jsonl"
  exit 0
fi

echo "unexpected mk args: $*" >&2
exit 2
""",
        encoding="utf-8",
    )
    mk_stub.chmod(0o755)

    out_dir = repo_root / "out" / "buyer_pack"
    env = {
        **os.environ,
        "PATH": f"{test_bin}:{os.environ.get('PATH', '')}",
        "MK_CALLS_LOG": str(calls_log),
    }

    cp = subprocess.run(
        ["/bin/bash", str(script), "--out", str(out_dir)],
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )
    assert cp.returncode == 0, cp.stderr

    assert (out_dir / "plan" / "closed_loop_latest.json").exists()
    assert (out_dir / "verify" / "k8s_verify_latest.json").exists()
    assert (out_dir / "preflight" / "preflight_latest.json").exists()
    assert (out_dir / "eval" / "eval_latest.json").exists()
    assert (out_dir / "watch" / "watch_latest.json").exists()
    assert (out_dir / "roi" / "roi_latest.json").exists()
    assert (out_dir / "dryrun" / "closed_loop_latest.json").exists()
    assert (out_dir / "dryrun" / "k8s_plan.json").exists()
    assert (out_dir / "export" / "bundle_manifest.json").exists()
    assert (out_dir / "export" / "bundle.tar.gz").exists()

    calls = calls_log.read_text(encoding="utf-8").splitlines()
    assert len(calls) == 3
    assert calls[0] == "doctor"
    assert calls[1].startswith("quickstart --out ")
    assert calls[2].startswith("closed-loop run ")
    assert all("handoff-pack" not in call for call in calls)
    assert all("procurement-pack" not in call for call in calls)
    assert not (out_dir / "handoff_pack.tar.gz").exists()
    assert not (out_dir / "procurement_pack.tar.gz").exists()

