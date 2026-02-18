import subprocess
from pathlib import Path


def test_cli_version_flag(mk_path: Path) -> None:
    p = subprocess.run([str(mk_path), "--version"], capture_output=True, text=True)
    assert p.returncode == 0
    assert "modekeeper" in (p.stdout or "")
