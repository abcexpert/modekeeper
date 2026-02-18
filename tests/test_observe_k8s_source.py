import json
import os
import subprocess
from pathlib import Path


def _write_fake_kubectl(path: Path, log_output: str) -> None:
    script = f"""#!/usr/bin/env bash
set -Eeuo pipefail

if [[ "$1" == "logs" ]]; then
  cat <<'EOF'
{log_output}
EOF
  exit 0
fi

echo "unexpected args: $*" >&2
exit 1
"""
    path.write_text(script, encoding="utf-8")
    path.chmod(0o755)


def test_observe_k8s_logs_source(tmp_path: Path, mk_path: Path) -> None:
    kubectl = tmp_path / "kubectl"
    log_output = "\n".join(
        [
            '{"ts":"2026-01-01T00:00:00Z","step_time_ms":120,"loss":1.0}',
            '{"ts":"2026-01-01T00:00:01Z","step_time_ms":130}',
        ]
    )
    _write_fake_kubectl(kubectl, log_output)

    out_dir = tmp_path / "observe_out"
    env = {**os.environ, "KUBECTL": str(kubectl)}
    subprocess.run(
        [
            str(mk_path),
            "observe",
            "--duration",
            "10s",
            "--source",
            "k8s",
            "--k8s-namespace",
            "ns1",
            "--k8s-deployment",
            "dep1",
            "--container",
            "trainer",
            "--out",
            str(out_dir),
        ],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )

    latest = json.loads((out_dir / "observe_latest.json").read_text(encoding="utf-8"))
    assert latest.get("sample_count") == 2
