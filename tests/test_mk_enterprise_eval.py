import os
import shutil
import subprocess
from pathlib import Path


def test_mk_enterprise_eval_minimal_runtime_contract(tmp_path: Path) -> None:
    source_repo = Path(__file__).resolve().parents[1]
    source_script = source_repo / "bin" / "mk-enterprise-eval"

    repo_root = tmp_path / "repo"
    (repo_root / "bin").mkdir(parents=True)

    script = repo_root / "bin" / "mk-enterprise-eval"
    shutil.copy2(source_script, script)
    script.chmod(0o755)

    calls_log = tmp_path / "calls.log"
    procurement_script = repo_root / "bin" / "mk-procurement-pack"
    procurement_script.write_text(
        """#!/usr/bin/env bash
set -Eeuo pipefail

printf '%s\\n' "$0 $*" >> "${MK_CALLS_LOG:?}"

ROOT="report/procurement_pack"
mkdir -p "$ROOT/buyer_pack/plan" "$ROOT/buyer_pack/verify" "$ROOT/buyer_pack/dryrun"
echo "stub tarball" >"$ROOT/procurement_pack.tar.gz"
echo "stub checksums" >"$ROOT/checksums.sha256"
echo "{}" >"$ROOT/buyer_pack/plan/closed_loop_latest.json"
echo "{}" >"$ROOT/buyer_pack/verify/k8s_verify_latest.json"
echo "{}" >"$ROOT/buyer_pack/dryrun/closed_loop_latest.json"
echo "{}" >"$ROOT/buyer_pack/dryrun/k8s_plan.json"
""",
        encoding="utf-8",
    )
    procurement_script.chmod(0o755)

    env = {**os.environ, "MK_CALLS_LOG": str(calls_log)}
    cp = subprocess.run(
        ["/bin/bash", str(script)],
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )
    assert cp.returncode == 0, cp.stderr

    out_root = repo_root / "report" / "enterprise_eval"
    index = out_root / "index.md"
    assert index.exists()
    body = index.read_text(encoding="utf-8")
    assert "Enterprise Evaluation Index" in body
    assert "report/procurement_pack/procurement_pack.tar.gz" in body
    assert "report/procurement_pack/checksums.sha256" in body
    assert "buyer_pack/plan/closed_loop_latest.json" in body
    assert "buyer_pack/verify/k8s_verify_latest.json" in body
    assert "buyer_pack/dryrun/closed_loop_latest.json" in body
    assert "buyer_pack/dryrun/k8s_plan.json" in body
    assert "handoff-pack" not in body

    calls = calls_log.read_text(encoding="utf-8").splitlines()
    assert len(calls) == 1
    assert calls[0].strip() == "./bin/mk-procurement-pack"
