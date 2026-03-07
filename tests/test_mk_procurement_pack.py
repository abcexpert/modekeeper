import os
import shutil
import subprocess
from pathlib import Path


def test_mk_procurement_pack_demo_kind_missing_kind_binary(tmp_path: Path) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    script = repo_root / "bin" / "mk-procurement-pack"

    test_bin = tmp_path / "bin"
    test_bin.mkdir()
    for cmd in ("rm", "mkdir"):
        src = shutil.which(cmd)
        assert src, f"missing required test command: {cmd}"
        (test_bin / cmd).symlink_to(src)

    env = {
        **os.environ,
        "MK_PACK_DEMO_KIND": "1",
        "PATH": str(test_bin),
    }
    cp = subprocess.run(
        ["/bin/bash", str(script)],
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )

    assert cp.returncode == 2
    assert "kind" in cp.stderr.lower()


def test_mk_procurement_pack_checksums_include_tarball(tmp_path: Path) -> None:
    source_repo = Path(__file__).resolve().parents[1]
    source_script = source_repo / "bin" / "mk-procurement-pack"

    repo_root = tmp_path / "repo"
    (repo_root / "bin").mkdir(parents=True)
    (repo_root / "docs").mkdir(parents=True)

    script = repo_root / "bin" / "mk-procurement-pack"
    shutil.copy2(source_script, script)
    script.chmod(0o755)

    buyer_pack_script = repo_root / "bin" / "mk-buyer-pack"
    buyer_pack_script.write_text(
        """#!/usr/bin/env bash
set -Eeuo pipefail
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
echo "stub buyer pack" >"$OUT/manifest.txt"
""",
        encoding="utf-8",
    )
    buyer_pack_script.chmod(0o755)

    required_files = [
        "README.md",
        "LICENSE",
        "docs/ROADMAP_PUBLIC.md",
        "docs/SECURITY_POSTURE.md",
        "docs/COMPLIANCE_MATRIX.md",
        "docs/SECURITY_QA.md",
        "docs/THREAT_MODEL.md",
        "docs/BUYER_PROOF_PACK.md",
        "docs/WORKFLOW.md",
        "docs/RELEASE.md",
        "docs/DISTRIBUTION_POLICY.md",
        "docs/product.md",
        "docs/STATUS.md",
    ]
    for rel_path in required_files:
        file_path = repo_root / rel_path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(f"test fixture for {rel_path}\n", encoding="utf-8")

    cp = subprocess.run(
        ["/bin/bash", str(script)],
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
        env=os.environ.copy(),
    )
    assert cp.returncode == 0, cp.stderr

    checksums_file = repo_root / "report" / "procurement_pack" / "checksums.sha256"
    checksums = checksums_file.read_text(encoding="utf-8")
    assert "procurement_pack.tar.gz" in checksums
