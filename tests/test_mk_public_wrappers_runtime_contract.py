import os
import shutil
import subprocess
import sys
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def test_mk_doctor_wrapper_pass_runtime_contract(tmp_path: Path) -> None:
    script = _repo_root() / "bin" / "mk-doctor"

    test_bin = tmp_path / "bin"
    test_bin.mkdir(parents=True)

    python3_src = shutil.which("python3")
    assert python3_src, "python3 is required for this test"
    (test_bin / "python3").symlink_to(python3_src)

    mk_stub = test_bin / "mk"
    mk_stub.write_text(
        """#!/usr/bin/env bash
set -Eeuo pipefail
if [[ "${1:-}" == "--help" ]]; then
  exit 0
fi
exit 0
""",
        encoding="utf-8",
    )
    mk_stub.chmod(0o755)

    kubectl_stub = test_bin / "kubectl"
    kubectl_stub.write_text("#!/usr/bin/env bash\nexit 0\n", encoding="utf-8")
    kubectl_stub.chmod(0o755)

    home_dir = tmp_path / "home"
    (home_dir / ".modekeeper" / "venv" / "bin").mkdir(parents=True)
    (home_dir / ".modekeeper" / "venv" / "bin" / "python").symlink_to(python3_src)
    (home_dir / ".kube").mkdir(parents=True)
    (home_dir / ".kube" / "config").write_text("apiVersion: v1\n", encoding="utf-8")

    env = {
        **os.environ,
        "HOME": str(home_dir),
        "PATH": f"{test_bin}:{os.environ.get('PATH', '')}",
    }
    cp = subprocess.run(
        ["/bin/bash", str(script)],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )
    assert cp.returncode == 0, cp.stderr
    assert "Doctor result: PASS" in cp.stdout
    assert "PASS mk runnable" in cp.stdout


def test_mk_doctor_wrapper_rejects_unknown_arg(tmp_path: Path) -> None:
    script = _repo_root() / "bin" / "mk-doctor"
    cp = subprocess.run(
        ["/bin/bash", str(script), "--nope"],
        check=False,
        capture_output=True,
        text=True,
        env=os.environ.copy(),
    )
    assert cp.returncode == 2
    assert "ERROR: unknown argument: --nope" in cp.stderr
    assert "usage: ./bin/mk-doctor" in cp.stderr


def test_mk_install_wrapper_fails_without_home() -> None:
    script = _repo_root() / "bin" / "mk-install"
    env = os.environ.copy()
    env.pop("HOME", None)
    cp = subprocess.run(
        ["/bin/bash", str(script)],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )
    assert cp.returncode == 2
    assert "ERROR: HOME is not set" in cp.stderr


def test_mk_install_wrapper_fails_without_python3(tmp_path: Path) -> None:
    script = _repo_root() / "bin" / "mk-install"
    empty_bin = tmp_path / "empty-bin"
    empty_bin.mkdir(parents=True)
    env = {
        **os.environ,
        "HOME": str(tmp_path / "home"),
        "PATH": str(empty_bin),
    }
    cp = subprocess.run(
        ["/bin/bash", str(script)],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )
    assert cp.returncode == 2
    assert "ERROR: python3 is required" in cp.stderr


def test_mk_status_wrapper_renders_status_from_tickets(tmp_path: Path) -> None:
    script = _repo_root() / "bin" / "mk-status"
    tickets = tmp_path / "TICKETS.md"
    out_path = tmp_path / "STATUS.md"
    tickets.write_text(
        """- ID: MK-100
Title: Export buyer pack
Status: DONE

- ID: MK-101
Title: Verify gate safety checks
Status: IN_PROGRESS
""",
        encoding="utf-8",
    )

    cp = subprocess.run(
        [sys.executable, str(script), "--tickets", str(tickets), "--out", str(out_path)],
        check=False,
        capture_output=True,
        text=True,
        env=os.environ.copy(),
    )
    assert cp.returncode == 0, cp.stderr
    assert out_path.exists()

    body = out_path.read_text(encoding="utf-8")
    assert "# ModeKeeper Status" in body
    assert f"_Source: `{tickets.as_posix()}`_" in body
    assert "- TOTAL: 2" in body
    assert "- DONE: 1" in body
    assert "- IN_PROGRESS: 1" in body
    assert "MK-101" in body


def test_mk_status_wrapper_defaults_missing_title_and_status(tmp_path: Path) -> None:
    script = _repo_root() / "bin" / "mk-status"
    tickets = tmp_path / "TICKETS.md"
    out_path = tmp_path / "STATUS.md"
    tickets.write_text(
        """- ID: MK-102
Status: IN_PROGRESS

- ID: MK-103
Title: Add remaining wrapper contract tests
""",
        encoding="utf-8",
    )

    cp = subprocess.run(
        [sys.executable, str(script), "--tickets", str(tickets), "--out", str(out_path)],
        check=False,
        capture_output=True,
        text=True,
        env=os.environ.copy(),
    )
    assert cp.returncode == 0, cp.stderr
    body = out_path.read_text(encoding="utf-8")
    assert "MK-102 — (missing title)" in body
    assert "### UNKNOWN (1)" in body
