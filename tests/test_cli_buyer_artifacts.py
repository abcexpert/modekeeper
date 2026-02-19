import json
import subprocess
from pathlib import Path


def _run(mk: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [str(mk), *args],
        text=True,
        capture_output=True,
    )


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def test_cli_buyer_reports_top_level_commands(tmp_path: Path, mk_path: Path) -> None:
    root = tmp_path / "buyer_pack"
    plan_path = root / "plan" / "closed_loop_latest.json"
    verify_path = root / "verify" / "k8s_verify_latest.json"
    _write_json(
        plan_path,
        {
            "schema_version": "v0",
            "k8s_namespace": "default",
            "k8s_deployment": "trainer",
            "sample_count": 8,
            "signals": {"notes": ["gpu_saturated"]},
            "environment": {"unstable": False, "nodes_seen": ["node-a"], "gpu_models_seen": ["A100"]},
            "proposed": [{"knob": "grad_accum_steps", "target": 8}],
            "blocked_reasons": {"verify_failed": 0},
            "applied_reasons": {"dry_run": 0},
        },
    )
    _write_json(verify_path, {"ok": True, "verify_blocker": None})

    cp = _run(mk_path, ["preflight", "--out", str(root / "preflight"), "--inputs-root", str(root)])
    assert cp.returncode == 0, cp.stderr
    cp = _run(mk_path, ["eval", "--out", str(root / "eval"), "--inputs-root", str(root)])
    assert cp.returncode == 0, cp.stderr
    cp = _run(mk_path, ["watch", "--out", str(root / "watch"), "--duration", "15", "--inputs-root", str(root)])
    assert cp.returncode == 0, cp.stderr
    cp = _run(mk_path, ["roi", "--out", str(root / "roi"), "--inputs-root", str(root)])
    assert cp.returncode == 0, cp.stderr

    for name in ("preflight", "eval", "watch", "roi"):
        latest = root / name / f"{name}_latest.json"
        assert latest.exists()
        assert (root / name / "summary.md").exists()
        ts_matches = list((root / name).glob(f"{name}_????????_??????.json"))
        assert ts_matches

    roi_latest = json.loads((root / "roi" / "roi_latest.json").read_text(encoding="utf-8"))
    assert roi_latest.get("inputs_root") == str(root.resolve())
    assert "ok" in roi_latest
    assert "notes" in roi_latest
