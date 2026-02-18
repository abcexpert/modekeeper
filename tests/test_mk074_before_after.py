import json
import subprocess
from pathlib import Path


def test_mk074_before_after_cli_deterministic(tmp_path: Path, mk_path: Path) -> None:
    observe_path = Path("tests/data/observe/bursty.jsonl")
    out_dir_a = tmp_path / "out_a"
    out_dir_b = tmp_path / "out_b"

    cp_a = subprocess.run(
        [
            str(mk_path),
            "roi",
            "mk074",
            "--observe-source",
            "file",
            "--observe-path",
            str(observe_path),
            "--out",
            str(out_dir_a),
        ],
        text=True,
        capture_output=True,
    )
    assert cp_a.returncode == 0, cp_a.stderr

    cp_b = subprocess.run(
        [
            str(mk_path),
            "roi",
            "mk074",
            "--observe-source",
            "file",
            "--observe-path",
            str(observe_path),
            "--out",
            str(out_dir_b),
        ],
        text=True,
        capture_output=True,
    )
    assert cp_b.returncode == 0, cp_b.stderr

    before_a = out_dir_a / "mk074_before_latest.json"
    after_a = out_dir_a / "mk074_after_latest.json"
    combined_a = out_dir_a / "mk074_before_after_latest.json"
    before_b = out_dir_b / "mk074_before_latest.json"
    after_b = out_dir_b / "mk074_after_latest.json"
    combined_b = out_dir_b / "mk074_before_after_latest.json"

    assert before_a.exists()
    assert after_a.exists()
    assert combined_a.exists()
    assert before_b.exists()
    assert after_b.exists()
    assert combined_b.exists()

    combined = json.loads(combined_a.read_text(encoding="utf-8"))
    assert combined.get("schema_version") == "mk074_before_after.v0"

    before = combined.get("before")
    after = combined.get("after")
    assert isinstance(before, dict)
    assert isinstance(after, dict)
    assert isinstance(before.get("timeline"), list)
    assert isinstance(after.get("timeline"), list)
    assert isinstance(before.get("summary"), dict)
    assert isinstance(after.get("summary"), dict)

    diff = combined.get("diff", {})
    assert diff.get("estimated_apply_steps_saved", -1) >= 0

    combined_text = json.dumps(combined, ensure_ascii=False, sort_keys=True)
    assert "latency_ms" not in combined_text
    assert "worker_latencies_ms" not in combined_text
    assert "samples" not in combined_text

    assert combined_a.read_text(encoding="utf-8") == combined_b.read_text(encoding="utf-8")

