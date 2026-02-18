from modekeeper.trainer.chart_runtime import _knob_lines


def test_knob_lines_are_filtered_and_sorted() -> None:
    pod = {
        "metadata": {
            "annotations": {
                "modekeeper/knob.zeta": "9",
                "modekeeper/knob.alpha": "1",
                "modekeeper/knob.foo": "bar",
                "other/value": "skip",
            }
        }
    }

    assert _knob_lines(pod) == [
        "modekeeper/knob.alpha=1",
        "modekeeper/knob.foo=bar",
        "modekeeper/knob.zeta=9",
    ]


def test_knob_lines_empty_when_annotations_missing() -> None:
    assert _knob_lines({}) == []
