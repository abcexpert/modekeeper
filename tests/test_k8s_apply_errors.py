import json
import subprocess
from pathlib import Path


def _read_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _assert_pro_required_out_dir(out_dir: Path) -> None:
    explain = out_dir / "explain.jsonl"
    assert explain.exists()

    events = _read_jsonl(explain)
    names = [e.get("event") for e in events]
    assert "k8s_apply_start" in names
    assert "k8s_apply_blocked" in names

    latest = out_dir / "k8s_apply_latest.json"
    assert latest.exists()
    report = json.loads(latest.read_text(encoding="utf-8"))
    assert report.get("block_reason") == "pro_required"


def test_k8s_apply_missing_plan_still_writes_pro_required_artifact(tmp_path: Path, mk_path: Path) -> None:
    out_dir = tmp_path / "out_missing"
    r = subprocess.run(
        [str(mk_path), "k8s", "apply", "--plan", str(tmp_path / "nope.json"), "--out", str(out_dir)],
        capture_output=True,
        text=True,
    )
    assert r.returncode == 2
    assert r.stderr.strip() == "PRO REQUIRED: k8s apply"
    _assert_pro_required_out_dir(out_dir)


def test_k8s_apply_invalid_json_still_writes_pro_required_artifact(tmp_path: Path, mk_path: Path) -> None:
    plan = tmp_path / "bad.json"
    plan.write_text("{not json", encoding="utf-8")

    out_dir = tmp_path / "out_bad"
    r = subprocess.run(
        [str(mk_path), "k8s", "apply", "--plan", str(plan), "--out", str(out_dir)],
        capture_output=True,
        text=True,
    )
    assert r.returncode == 2
    assert r.stderr.strip() == "PRO REQUIRED: k8s apply"
    _assert_pro_required_out_dir(out_dir)


def test_k8s_apply_invalid_item_still_writes_pro_required_artifact(tmp_path: Path, mk_path: Path) -> None:
    plan = tmp_path / "bad_item.json"
    plan.write_text(json.dumps([{"namespace": "ns1", "patch": "nope"}]), encoding="utf-8")

    out_dir = tmp_path / "out_bad_item"
    r = subprocess.run(
        [str(mk_path), "k8s", "apply", "--plan", str(plan), "--out", str(out_dir)],
        capture_output=True,
        text=True,
    )
    assert r.returncode == 2
    assert r.stderr.strip() == "PRO REQUIRED: k8s apply"
    _assert_pro_required_out_dir(out_dir)
