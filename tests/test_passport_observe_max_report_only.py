import subprocess
from pathlib import Path


def test_observe_max_report_only_cli_file_source(tmp_path: Path, mk_path: Path) -> None:
    out_dir = tmp_path / "out"
    observe_path = Path("tests/data/observe/bursty.jsonl")

    cp = subprocess.run(
        [
            str(mk_path),
            "passport",
            "observe-max-report",
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

    report_path = out_dir / "observe_max_latest.json"
    passport_path = out_dir / "passport_observe_max_latest.json"
    assert report_path.exists()
    assert not passport_path.exists()

    report_text = report_path.read_text(encoding="utf-8").lower()
    forbidden_tokens = [
        "chord",
        "allowed_chords",
        "burst-absorb",
        "recover",
        "relock",
        "knob",
        "target",
        "k8s_plan",
        "patch",
        "apply",
        "actions",
        "decision_trace",
    ]
    for token in forbidden_tokens:
        assert token not in report_text
