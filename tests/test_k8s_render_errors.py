import json
import subprocess
from pathlib import Path


def _read_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _assert_error_out_dir(out_dir: Path, *, expected_kind: str) -> None:
    explain = out_dir / "explain.jsonl"
    assert explain.exists()

    events = _read_jsonl(explain)
    names = [e.get("event") for e in events]

    assert "k8s_render_start" in names
    assert "k8s_render_error" in names

    last_err = next(e for e in reversed(events) if e.get("event") == "k8s_render_error")
    payload = last_err.get("payload") or {}
    assert payload.get("kind") == expected_kind

    # На ошибке не должно быть частичных артефактов
    assert not (out_dir / "k8s_plan.kubectl.sh").exists()
    assert not (out_dir / "k8s_render_latest.json").exists()
    assert not any(out_dir.glob("k8s_render_*.json"))


def test_k8s_render_missing_plan_still_writes_explain(tmp_path: Path, mk_path: Path) -> None:
    out_dir = tmp_path / "out_missing"
    mk = mk_path
    r = subprocess.run(
        [str(mk), "k8s", "render", "--plan", str(tmp_path / "nope.json"), "--out", str(out_dir)],
        capture_output=True,
        text=True,
    )
    assert r.returncode == 2
    _assert_error_out_dir(out_dir, expected_kind="not_found")


def test_k8s_render_invalid_json(tmp_path: Path, mk_path: Path) -> None:
    plan = tmp_path / "bad.json"
    plan.write_text("{not json", encoding="utf-8")

    out_dir = tmp_path / "out_bad"
    mk = mk_path
    r = subprocess.run(
        [str(mk), "k8s", "render", "--plan", str(plan), "--out", str(out_dir)],
        capture_output=True,
        text=True,
    )
    assert r.returncode == 2
    _assert_error_out_dir(out_dir, expected_kind="invalid_json")


def test_k8s_render_non_list_plan(tmp_path: Path, mk_path: Path) -> None:
    plan = tmp_path / "obj.json"
    plan.write_text(json.dumps({"hello": "world"}), encoding="utf-8")

    out_dir = tmp_path / "out_obj"
    mk = mk_path
    r = subprocess.run(
        [str(mk), "k8s", "render", "--plan", str(plan), "--out", str(out_dir)],
        capture_output=True,
        text=True,
    )
    assert r.returncode == 2
    _assert_error_out_dir(out_dir, expected_kind="invalid_shape")


def test_k8s_render_invalid_item(tmp_path: Path, mk_path: Path) -> None:
    plan = tmp_path / "bad_item.json"
    plan.write_text(json.dumps([{"namespace": "ns1", "patch": "nope"}]), encoding="utf-8")

    out_dir = tmp_path / "out_bad_item"
    mk = mk_path
    r = subprocess.run(
        [str(mk), "k8s", "render", "--plan", str(plan), "--out", str(out_dir)],
        capture_output=True,
        text=True,
    )
    assert r.returncode == 2
    _assert_error_out_dir(out_dir, expected_kind="invalid_item")
