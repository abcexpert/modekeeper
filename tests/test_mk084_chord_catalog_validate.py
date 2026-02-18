import json
import subprocess
from pathlib import Path


def test_mk084_chords_validate_ok(tmp_path: Path, mk_path: Path) -> None:
    catalog_path = tmp_path / "catalog_ok.json"
    out_dir = tmp_path / "out"
    catalog_path.write_text(
        json.dumps(
            {
                "schema_version": "chord_catalog.v1",
                "chords": [
                    {
                        "id": "X-SAFE",
                        "intent": "Test safe chord",
                        "risk_tier": "safe",
                        "required_signals": ["drift"],
                        "invariants": ["keep_global_batch_stable"],
                        "knobs_touched": ["concurrency"],
                    }
                ],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    cp = subprocess.run(
        [
            str(mk_path),
            "chords",
            "validate",
            "--catalog",
            str(catalog_path),
            "--out",
            str(out_dir),
        ],
        text=True,
        capture_output=True,
    )
    assert cp.returncode == 0

    report_path = out_dir / "chords_validate_latest.json"
    assert report_path.exists()
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report == {
        "schema_version": "chords_validate.v0",
        "ok": True,
        "errors": [],
        "chord_count": 1,
        "chord_ids": ["X-SAFE"],
    }


def test_mk084_chords_validate_bad(tmp_path: Path, mk_path: Path) -> None:
    catalog_path = tmp_path / "catalog_bad.json"
    out_dir = tmp_path / "out"
    catalog_path.write_text(
        json.dumps(
            {
                "schema_version": "chord_catalog.v1",
                "chords": [
                    {
                        "id": "BROKEN",
                        "intent": 123,
                        "risk_tier": "safe",
                        "required_signals": "drift",
                        "knobs_touched": [],
                    }
                ],
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    cp = subprocess.run(
        [
            str(mk_path),
            "chords",
            "validate",
            "--catalog",
            str(catalog_path),
            "--out",
            str(out_dir),
        ],
        text=True,
        capture_output=True,
    )
    assert cp.returncode == 2

    report = json.loads((out_dir / "chords_validate_latest.json").read_text(encoding="utf-8"))
    assert report.get("schema_version") == "chords_validate.v0"
    assert report.get("ok") is False
    assert report.get("chord_count") == 1
    assert report.get("chord_ids") == ["BROKEN"]
    assert isinstance(report.get("errors"), list)
    assert report["errors"]
