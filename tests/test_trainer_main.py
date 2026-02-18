from modekeeper.trainer.__main__ import _knobs_kv, _to_positive_float


def test_knobs_kv_is_sorted_and_compact() -> None:
    knobs = {
        "microbatch_size": "32",
        "concurrency": "4",
        "grad_accum_steps": "8",
    }

    assert _knobs_kv(knobs) == "concurrency=4 grad_accum_steps=8 microbatch_size=32"


def test_to_positive_float_uses_default_for_invalid_values() -> None:
    assert _to_positive_float("1.5", default=2.0) == 1.5
    assert _to_positive_float("0", default=2.0) == 2.0
    assert _to_positive_float("-3", default=2.0) == 2.0
    assert _to_positive_float("nope", default=2.0) == 2.0
    assert _to_positive_float(None, default=2.0) == 2.0
