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


def _write_plan(plan_path: Path) -> None:
    plan_path.write_text(
        json.dumps(
            [
                {"namespace": "ns1", "name": "dep1", "patch": {"spec": {"replicas": 2}}},
            ]
        ),
        encoding="utf-8",
    )


def _read_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _assert_pro_required(out_dir: Path, stderr: str) -> None:
    assert stderr.strip() == "PRO REQUIRED: k8s apply"
    report = json.loads((out_dir / "k8s_apply_latest.json").read_text(encoding="utf-8"))
    assert report.get("would_apply") is False
    assert report.get("block_reason") == "pro_required"
    assert report.get("reason") == "pro_required"
    events = _read_jsonl(out_dir / "explain.jsonl")
    blocked = [e for e in events if e.get("event") == "k8s_apply_blocked"]
    assert blocked
    assert (blocked[-1].get("payload") or {}).get("reason") == "pro_required"


def test_k8s_apply_blocked_public_default(tmp_path: Path, mk_path: Path) -> None:
    plan = tmp_path / "plan.json"
    _write_plan(plan)
    out_dir = tmp_path / "out"

    cp = _run(mk_path, ["k8s", "apply", "--plan", str(plan), "--out", str(out_dir)])
    assert cp.returncode == 2
    _assert_pro_required(out_dir, cp.stderr)


def test_k8s_apply_blocked_even_with_internal_override(tmp_path: Path, mk_path: Path) -> None:
    plan = tmp_path / "plan.json"
    _write_plan(plan)
    out_dir = tmp_path / "out"

    cp = _run(
        mk_path,
        ["k8s", "apply", "--plan", str(plan), "--out", str(out_dir)],
        env={"MODEKEEPER_PAID": "1", "MODEKEEPER_INTERNAL_OVERRIDE": "1"},
    )
    assert cp.returncode == 2
    _assert_pro_required(out_dir, cp.stderr)
