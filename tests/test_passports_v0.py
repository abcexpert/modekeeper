import subprocess
from pathlib import Path

from modekeeper.passports.v0 import load_template, list_templates


def test_all_templates_validate() -> None:
    names = list_templates()
    assert names
    for name in names:
        passport = load_template(name)
        assert passport.schema_version == "passport.v0"
        assert passport.name == name


def test_mk_passport_templates_cli(tmp_path: Path, mk_path: Path) -> None:
    cp = subprocess.run(
        [str(mk_path), "passport", "templates"],
        text=True,
        capture_output=True,
        cwd=tmp_path,
    )
    assert cp.returncode == 0

    output = set(line.strip() for line in cp.stdout.splitlines() if line.strip())
    expected = {"pilot", "safe", "perf", "cost", "io", "comm", "recovery"}
    assert expected.issubset(output)


def test_mk_passport_validate_valid_template_file(tmp_path: Path, mk_path: Path) -> None:
    valid_file = Path(__file__).resolve().parents[1] / "src" / "modekeeper" / "passports" / "templates" / "safe.json"
    cp = subprocess.run(
        [str(mk_path), "passport", "validate", "--file", str(valid_file)],
        text=True,
        capture_output=True,
        cwd=tmp_path,
    )
    assert cp.returncode == 0
    assert cp.stderr.strip() == ""


def test_mk_passport_validate_invalid_json(tmp_path: Path, mk_path: Path) -> None:
    broken = tmp_path / "broken_passport.json"
    broken.write_text("{not-json", encoding="utf-8")

    cp = subprocess.run(
        [str(mk_path), "passport", "validate", "--file", str(broken)],
        text=True,
        capture_output=True,
    )
    assert cp.returncode == 2
    assert "ERROR:" in cp.stderr
