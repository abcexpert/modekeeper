import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path


def test_observe_file_source_epoch_jsonl(tmp_path: Path, mk_path: Path) -> None:
    metrics_path = tmp_path / "metrics_epoch.jsonl"
    ts_epoch_s = int(datetime.now(timezone.utc).timestamp())
    ts_epoch_ms = ts_epoch_s * 1000 + 123

    rows = [
        {"ts": ts_epoch_s, "step_time_ms": 120, "loss": 1.0},
        {"ts": ts_epoch_ms, "step_time_ms": 130, "loss": 1.1},
        {"ts": ts_epoch_s, "step_time_ms": 125, "loss": 1.05},
    ]
    metrics_path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")

    out_dir = tmp_path / "epoch_jsonl_out"
    mk = mk_path
    subprocess.run(
        [str(mk), "observe", "--duration", "1s", "--source", "file", "--path", str(metrics_path), "--out", str(out_dir)],
        check=True,
        capture_output=True,
        text=True,
    )

    explain = (out_dir / "explain.jsonl").read_text(encoding="utf-8").splitlines()
    assert any('"event": "observe_source"' in line for line in explain)

    latest = json.loads((out_dir / "observe_latest.json").read_text(encoding="utf-8"))
    assert latest.get("sample_count") == 3


def test_observe_file_source_epoch_csv(tmp_path: Path, mk_path: Path) -> None:
    metrics_path = tmp_path / "metrics_epoch.csv"
    ts_epoch_s = int(datetime.now(timezone.utc).timestamp())
    ts_epoch_ms = ts_epoch_s * 1000 + 456

    metrics_path.write_text(
        "ts,step_time_ms,loss\n"
        f"{ts_epoch_s},120,1.0\n"
        f"{ts_epoch_ms},130,1.1\n"
        f"{ts_epoch_s},125,1.05\n",
        encoding="utf-8",
    )

    out_dir = tmp_path / "epoch_csv_out"
    mk = mk_path
    subprocess.run(
        [str(mk), "observe", "--duration", "1s", "--source", "file", "--path", str(metrics_path), "--out", str(out_dir)],
        check=True,
        capture_output=True,
        text=True,
    )

    explain = (out_dir / "explain.jsonl").read_text(encoding="utf-8").splitlines()
    assert any('"event": "observe_source"' in line for line in explain)

    latest = json.loads((out_dir / "observe_latest.json").read_text(encoding="utf-8"))
    assert latest.get("sample_count") == 3
