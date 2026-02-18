# --- test import path bootstrap (src/ layout) ---
import sys as _sys
from pathlib import Path as _Path

_SRC = _Path(__file__).resolve().parents[1] / "src"
if _SRC.is_dir():
    _p = str(_SRC)
    if _p not in _sys.path:
        _sys.path.insert(0, _p)
# --- end bootstrap ---

import sys
import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def mk_path() -> Path:
    repo_root = Path(__file__).resolve().parents[1]
    local = repo_root / ".venv" / "bin" / "mk"
    if local.exists():
        return local

    # Use a repo-local shim when local venv entrypoint is unavailable.
    shim_dir = Path(tempfile.mkdtemp(prefix="mk-shim-"))
    shim = shim_dir / "mk"
    shim.write_text(
        f"""#!/usr/bin/env bash
set -Eeuo pipefail
export PYTHONPATH=\"{repo_root}/src${{PYTHONPATH:+:${{PYTHONPATH}}}}\"
exec \"{sys.executable}\" -c 'import sys; from modekeeper.cli import main; raise SystemExit(main())' \"$@\"
""",
        encoding="utf-8",
    )
    shim.chmod(0o755)
    return shim
