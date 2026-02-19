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
