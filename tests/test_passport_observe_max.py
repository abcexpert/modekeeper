import json
import subprocess
from pathlib import Path

from modekeeper.passports.v0 import load_passport


def test_passport_observe_max_cli_file_source(tmp_path: Path, mk_path: Path) -> None:
    out_dir = tmp_path / "out"
    observe_path = Path("tests/data/observe/bursty.jsonl")

    cp = subprocess.run(
        [
            str(mk_path),
            "passport",
            "observe-max",
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

    passport_path = out_dir / "passport_observe_max_latest.json"
    report_path = out_dir / "observe_max_latest.json"
    assert passport_path.exists()
    assert report_path.exists()

    passport = load_passport(passport_path)
    assert passport.schema_version == "passport.v0"
    assert passport.name == "observe_max"
    assert passport.gates.get("apply") is False

    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report.get("schema_version") == "observe_max.v0"
    assert isinstance(report.get("coverage"), dict)
    assert isinstance(report.get("recommendation"), dict)

    report_text = json.dumps(report, ensure_ascii=False, sort_keys=True)
    assert "tests/data" not in report_text
    assert "namespace" not in report_text
    assert "pod" not in report_text
    assert "container" not in report_text
    assert "2026-" not in report_text
    assert "samples" not in report_text

    out_dir_2 = tmp_path / "out_2"
    cp2 = subprocess.run(
        [
            str(mk_path),
            "passport",
            "observe-max",
            "--observe-source",
            "file",
            "--observe-path",
            str(observe_path),
            "--out",
            str(out_dir_2),
        ],
        text=True,
        capture_output=True,
    )
    assert cp2.returncode == 0, cp2.stderr

    passport_text_1 = passport_path.read_text(encoding="utf-8")
    passport_text_2 = (out_dir_2 / "passport_observe_max_latest.json").read_text(encoding="utf-8")
    report_text_1 = report_path.read_text(encoding="utf-8")
    report_text_2 = (out_dir_2 / "observe_max_latest.json").read_text(encoding="utf-8")
    assert passport_text_1 == passport_text_2
    assert report_text_1 == report_text_2
