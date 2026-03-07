import json
import subprocess
from pathlib import Path


def test_proof_matrix_replay_harness_runs_three_proof_scenarios(
    tmp_path: Path, mk_path: Path
) -> None:
    out_dir = tmp_path / "proof_matrix"
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "proof-matrix-replay.sh"

    cp = subprocess.run(
        [
            "bash",
            str(script_path),
            "--out",
            str(out_dir),
        ],
        text=True,
        capture_output=True,
        env={"MK_BIN": str(mk_path)},
        check=False,
    )
    assert cp.returncode == 0, cp.stderr

    matrix = json.loads((out_dir / "proof_matrix.json").read_text(encoding="utf-8"))
    assert matrix.get("schema_version") == "v1_internal"
    assert matrix.get("harness") == "proof_matrix_replay"
    assert matrix.get("scenario_order") == [
        "replica_overprovisioning",
        "cpu_pressure",
        "memory_pressure",
    ]
    assert matrix.get("all_passed") is True
    assert matrix.get("passed_count") == 3
    assert matrix.get("failed_count") == 0

    rows = matrix.get("rows", [])
    assert [row.get("scenario") for row in rows] == matrix.get("scenario_order")
    assert all(row.get("passed") is True for row in rows)

    matrix_md = (out_dir / "proof_matrix.md").read_text(encoding="utf-8")
    assert "| replica_overprovisioning | PASS | signal_found |" in matrix_md
    assert "| cpu_pressure | PASS | signal_found |" in matrix_md
    assert "| memory_pressure | PASS | signal_found |" in matrix_md
