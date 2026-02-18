import json

from modekeeper.adapters import lightning


def test_lightning_adapter_import(tmp_path) -> None:
    callback = lightning.build_lightning_callback(tmp_path)
    if not lightning.LIGHTNING_AVAILABLE:
        assert callback is None
        return

    assert callback is not None
    callback.on_fit_end(None, None)
    explain_path = tmp_path / "explain.jsonl"
    assert explain_path.exists()
    last_line = explain_path.read_text(encoding="utf-8").splitlines()[-1]
    record = json.loads(last_line)
    assert record["event"] == "pl_fit_end"
