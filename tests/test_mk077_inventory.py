import json
import os
import subprocess
from pathlib import Path


def _run(mk: Path, args: list[str], env: dict | None = None) -> subprocess.CompletedProcess[str]:
    process_env = os.environ.copy()
    if env:
        process_env.update(env)
    return subprocess.run([str(mk), *args], text=True, capture_output=True, env=process_env)


def test_mk077_fleet_inventory_with_path_stub(tmp_path: Path, mk_path: Path) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    kubectl = bin_dir / "kubectl"
    kubectl.write_text(
        """#!/usr/bin/env bash
set -Eeuo pipefail

if [[ $# -eq 2 && "$1" == "config" && "$2" == "current-context" ]]; then
  echo "ctx-a"
  exit 0
fi

if [[ $# -eq 6 && "$1" == "--context" && "$2" == "ctx-a" && "$3" == "get" && "$4" == "namespaces" && "$5" == "-o" && "$6" == "json" ]]; then
  echo '{"items":[{"metadata":{"name":"z-ns"}},{"metadata":{"name":"default"}}]}'
  exit 0
fi

if [[ $# -eq 7 && "$1" == "--context" && "$2" == "ctx-a" && "$3" == "get" && "$4" == "deployments" && "$5" == "-A" && "$6" == "-o" && "$7" == "json" ]]; then
  echo '{"items":[{"metadata":{"namespace":"z-ns","name":"z-app"}},{"metadata":{"namespace":"default","name":"trainer"}},{"metadata":{"namespace":"default","name":"a-app"}}]}'
  exit 0
fi

echo "unexpected args: $*" >&2
exit 1
""",
        encoding="utf-8",
    )
    kubectl.chmod(0o755)

    out_dir = tmp_path / "out"
    env = {"PATH": f"{bin_dir}:{os.environ.get('PATH', '')}"}
    cp = _run(mk_path, ["fleet", "inventory", "--out", str(out_dir)], env=env)
    assert cp.returncode == 0

    latest = out_dir / "inventory_latest.json"
    assert latest.exists()
    data = json.loads(latest.read_text(encoding="utf-8"))
    assert data.get("schema") == "inventory.v0"
    assert data.get("contexts") == [
        {
            "context": "ctx-a",
            "deployments": [
                {"name": "a-app", "namespace": "default"},
                {"name": "trainer", "namespace": "default"},
                {"name": "z-app", "namespace": "z-ns"},
            ],
            "namespaces": ["default", "z-ns"],
        }
    ]
