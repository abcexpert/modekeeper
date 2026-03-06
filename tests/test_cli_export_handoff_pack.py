import json
import subprocess
import tarfile
from pathlib import Path


def _run(mk: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run([str(mk), *args], text=True, capture_output=True, check=False)


def test_export_handoff_pack_builds_expected_outputs(tmp_path: Path, mk_path: Path) -> None:
    in_dir = tmp_path / "in"
    (in_dir / "preflight").mkdir(parents=True)
    (in_dir / "eval").mkdir(parents=True)
    (in_dir / "watch").mkdir(parents=True)
    (in_dir / "roi").mkdir(parents=True)

    (in_dir / "preflight" / "preflight_latest.json").write_text(json.dumps({"ok": True}) + "\n", encoding="utf-8")
    (in_dir / "eval" / "eval_latest.json").write_text(json.dumps({"sample_count": 1}) + "\n", encoding="utf-8")
    (in_dir / "watch" / "watch_latest.json").write_text(
        json.dumps(
            {"duration_s": 1, "iterations_done": 1, "proposed_total": 0, "blocked_total": 0, "applied_total": 0}
        )
        + "\n",
        encoding="utf-8",
    )
    (in_dir / "roi" / "roi_latest.json").write_text(
        json.dumps({"ok": True, "opportunity_hours_est": 0, "proposed_actions_count": 0, "top_blocker": "n/a"}) + "\n",
        encoding="utf-8",
    )

    out_dir = tmp_path / "out"
    cp = _run(mk_path, ["export", "handoff-pack", "--in", str(in_dir), "--out", str(out_dir)])
    assert cp.returncode == 0, cp.stderr

    expected = [
        "handoff_pack.tar.gz",
        "handoff_manifest.json",
        "handoff_summary.md",
        "handoff_pack.checksums.sha256",
        "HANDOFF_VERIFY.sh",
        "README.md",
    ]
    for name in expected:
        assert (out_dir / name).exists(), name

    chk = (out_dir / "handoff_pack.checksums.sha256").read_text(encoding="utf-8")
    assert "handoff_pack.tar.gz" in chk
    assert "handoff_manifest.json" in chk
    assert "HANDOFF_VERIFY.sh" in chk

    verify = (out_dir / "HANDOFF_VERIFY.sh").read_text(encoding="utf-8")
    assert "sha256sum -c" in verify
    assert "tar -xOf" in verify

    tar_path = out_dir / "handoff_pack.tar.gz"
    with tarfile.open(tar_path, "r:gz") as tf:
        names = tf.getnames()
        assert "bundle_manifest.json" in names
        f = tf.extractfile("bundle_manifest.json")
        assert f is not None
        data = f.read()

    assert data == (out_dir / "handoff_manifest.json").read_bytes()
