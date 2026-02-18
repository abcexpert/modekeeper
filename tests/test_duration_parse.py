import argparse

import pytest

from modekeeper.cli import _parse_duration_ms


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("0.2s", 200),
        ("1.5s", 1500),
        ("250ms", 250),
        ("2", 2000),
        ("2s", 2000),
    ],
)
def test_parse_duration_ms_ok(value: str, expected: int) -> None:
    assert _parse_duration_ms(value) == expected


@pytest.mark.parametrize("value", ["abc", "1xs"])
def test_parse_duration_ms_invalid(value: str) -> None:
    with pytest.raises(argparse.ArgumentTypeError):
        _parse_duration_ms(value)
