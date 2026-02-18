import json
import subprocess
from pathlib import Path

from modekeeper.chords.v1 import SAFE_CHORD_IDS_V1


def test_mk062_safe_chords_v1_and_timeout_chord_separation(tmp_path: Path, mk_path: Path) -> None:
    assert list(SAFE_CHORD_IDS_V1) == [
        "NORMAL-HOLD",
        "DRIFT-RETUNE",
        "BURST-ABSORB",
        "INPUT-STRAGGLER",
        "RECOVER-RELOCK",
    ]

    out_dir = tmp_path / "mk062_closed_loop_out"
    observe_path = Path("tests/data/observe/bursty.jsonl")
    cp = subprocess.run(
        [
            str(mk_path),
            "closed-loop",
            "run",
            "--scenario",
            "drift",
            "--dry-run",
            "--observe-source",
            "file",
            "--observe-path",
            str(observe_path),
            "--out",
            str(out_dir),
        ],
        text=True,
        capture_output=True,
    )
    assert cp.returncode == 0, cp.stderr

    trace_path = out_dir / "decision_trace_latest.jsonl"
    assert trace_path.exists()

    safe_ids = set(SAFE_CHORD_IDS_V1)
    for line in trace_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        event = json.loads(line)
        actions = event.get("actions") or []
        assert isinstance(actions, list)
        for action in actions:
            if action.get("knob") != "timeout_ms":
                continue
            if "chord" not in action:
                continue
            assert action["chord"] not in safe_ids

