"""Test functions in heudiconv.bids module.
"""

from heudiconv.bids import (
    maybe_na,
    treat_age,
)


def test_maybe_na():
    for na in '', ' ', None, 'n/a', 'N/A', 'NA':
        assert maybe_na(na) == 'n/a'
    for notna in 0, 1, False, True, 'value':
        assert maybe_na(notna) == str(notna)


def test_treat_age():
    assert treat_age(0) == '0'
    assert treat_age('0') == '0'
    assert treat_age('0000') == '0'
    assert treat_age('0000Y') == '0'
    assert treat_age('000.1Y') == '0.1'
    assert treat_age('1M') == '0.08'
    assert treat_age('12M') == '1'
    assert treat_age('0000.1') == '0.1'
    assert treat_age(0000.1) == '0.1'