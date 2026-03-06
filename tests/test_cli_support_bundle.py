import subprocess
import tarfile
from pathlib import Path


def _run(mk: Path, args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run([str(mk), *args], text=True, capture_output=True, check=False)


def test_support_bundle_redacts_secrets_in_json(tmp_path: Path, mk_path: Path) -> None:
    in_dir = tmp_path / "in"
    (in_dir / "eval").mkdir(parents=True)
    secret = "Bearer SUPERSECRET_TOKEN_1234567890"
    (in_dir / "eval" / "eval_latest.json").write_text(
        '{\n  "ok": true,\n  "token": "abc",\n  "note": "%s"\n}\n' % secret,
        encoding="utf-8",
    )

    out_dir = tmp_path / "out"
    cp = _run(mk_path, ["support-bundle", "--in", str(in_dir), "--out", str(out_dir)])
    assert cp.returncode == 0, cp.stderr

    manifest = out_dir / "support_bundle_manifest.json"
    tar_path = out_dir / "support_bundle.tar.gz"
    summary = out_dir / "support_bundle_summary.md"
    assert manifest.exists()
    assert tar_path.exists()
    assert summary.exists()

    # Tar contains redacted eval_latest.json and must not include raw secret.
    with tarfile.open(tar_path, "r:gz") as tf:
        data = tf.extractfile("eval/eval_latest.json").read()  # type: ignore[union-attr]
    text = data.decode("utf-8", errors="replace")
    assert "SUPERSECRET_TOKEN_1234567890" not in text
    assert "<REDACTED>" in text
