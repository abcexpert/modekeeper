from modekeeper.trainer.knobs import parse_downward_annotations


def test_parse_downward_annotations_filters_and_unquotes() -> None:
    text = """
modekeeper/knob.concurrency="2"
modekeeper/knob.dataloader_prefetch_factor="4"
modekeeper/knob.note="has spaces and \\\"quotes\\\""
modekeeper/knob.empty=""
not-a-valid-line
other/key="ignored"
modekeeper/knob.unquoted=value
"""

    got = parse_downward_annotations(text)

    assert got == {
        "concurrency": "2",
        "dataloader_prefetch_factor": "4",
        "empty": "",
        "note": 'has spaces and "quotes"',
    }
