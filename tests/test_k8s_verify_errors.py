import json
import subprocess
from pathlib import Path


def _run(mk: Path, args: list[str], env: dict | None = None) -> subprocess.CompletedProcess[str]:
    e = None
    if env is not None:
        import os
        e = os.environ.copy()
        e.update(env)
    return subprocess.run([str(mk), *args], text=True, capture_output=True, env=e)


def _assert_no_verify_artifacts(out_dir: Path) -> None:
    assert not (out_dir / "k8s_verify_latest.json").exists()
    assert not any(out_dir.glob("k8s_verify_*.json"))


def test_k8s_verify_missing_plan_writes_explain_no_artifacts(mk_path: Path, tmp_path: Path) -> None:
    out_dir = tmp_path / "out"
    plan = tmp_path / "missing.json"
    cp = _run(mk_path, ["k8s", "verify", "--plan", str(plan), "--out", str(out_dir)])
    assert cp.returncode == 2
    assert (out_dir / "explain.jsonl").exists()
    _assert_no_verify_artifacts(out_dir)


def test_k8s_verify_invalid_json_writes_explain_no_artifacts(mk_path: Path, tmp_path: Path) -> None:
    out_dir = tmp_path / "out"
    plan = tmp_path / "plan.json"
    plan.write_text("{", encoding="utf-8")

    cp = _run(mk_path, ["k8s", "verify", "--plan", str(plan), "--out", str(out_dir)])
    assert cp.returncode == 2
    assert (out_dir / "explain.jsonl").exists()
    _assert_no_verify_artifacts(out_dir)


def test_k8s_verify_invalid_item_writes_explain_no_artifacts(mk_path: Path, tmp_path: Path) -> None:
    out_dir = tmp_path / "out"
    plan = tmp_path / "plan.json"
    plan.write_text(json.dumps([{"namespace": "", "name": "dep1", "patch": {}}]), encoding="utf-8")

    cp = _run(mk_path, ["k8s", "verify", "--plan", str(plan), "--out", str(out_dir)])
    assert cp.returncode == 2
    assert (out_dir / "explain.jsonl").exists()
    _assert_no_verify_artifacts(out_dir)


def test_k8s_verify_invalid_shape_writes_explain_no_artifacts(mk_path: Path, tmp_path: Path) -> None:
    out_dir = tmp_path / "out"
    plan = tmp_path / "plan.json"
    plan.write_text(json.dumps({"not": "a list"}), encoding="utf-8")

    cp = _run(mk_path, ["k8s", "verify", "--plan", str(plan), "--out", str(out_dir)])
    assert cp.returncode == 2
    assert (out_dir / "explain.jsonl").exists()
    _assert_no_verify_artifacts(out_dir)
