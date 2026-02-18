import json
import subprocess
from pathlib import Path


def _run_mk068(mk_path: Path, out_dir: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(mk_path), "demo", "mk068", "--out", str(out_dir)],
        text=True,
        capture_output=True,
    )


def _contains_subsequence(items: list[str], subseq: list[str]) -> bool:
    idx = 0
    for item in items:
        if item == subseq[idx]:
            idx += 1
            if idx == len(subseq):
                return True
    return False


def test_demo_mk068_cli_generates_safe_deterministic_artifact(tmp_path: Path, mk_path: Path) -> None:
    out_dir_a = tmp_path / "out_a"
    cp_a = _run_mk068(mk_path, out_dir_a)
    assert cp_a.returncode == 0

    report_a = out_dir_a / "mk068_demo_latest.json"
    assert report_a.exists()

    payload_a = json.loads(report_a.read_text(encoding="utf-8"))
    assert payload_a.get("schema_version") == "mk068_demo.v0"
    timeline = payload_a.get("timeline")
    assert isinstance(timeline, list)
    assert timeline

    for step in timeline:
        assert "mode" in step
        assert "chord" in step
        assert "blocked_reason" in step
        assert "changed_knobs" in step
        assert isinstance(step["changed_knobs"], list)

    phases = [str(step.get("phase")) for step in timeline]
    modes = [str(step.get("mode")) for step in timeline]
    assert _contains_subsequence(phases, ["NORMAL", "DRIFT", "BURST", "STRAGGLER", "RECOVER", "NORMAL"])
    assert _contains_subsequence(modes, ["NORMAL", "DRIFT", "BURST", "STRAGGLER", "RECOVER", "NORMAL"])

    out_dir_b = tmp_path / "out_b"
    cp_b = _run_mk068(mk_path, out_dir_b)
    assert cp_b.returncode == 0

    report_b = out_dir_b / "mk068_demo_latest.json"
    assert report_b.exists()
    assert report_a.read_text(encoding="utf-8") == report_b.read_text(encoding="utf-8")
