import pytest

from src.scripts.seed_from_csv import parse_int


@pytest.mark.parametrize(
    ("value", "expected"),
    [("92", 92), ("92.0", 92), ("", None), ("null", None), (None, None), ("abc", None)],
)
def test_parse_int_accepts_float_formatted_integers(value, expected):
    # The CSV snapshot stores metacritic as "92.0" because the column has blanks.
    assert parse_int(value) == expected
