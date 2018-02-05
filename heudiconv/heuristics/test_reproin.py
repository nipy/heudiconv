#
# Tests for reproin.py
#
from collections import OrderedDict
from .reproin import get_dups_marked


def test_get_dups_marked():
    no_dups = {('some',): [1]}
    assert get_dups_marked(no_dups) == no_dups

    assert get_dups_marked(
        OrderedDict([
            (('bu', 'du'), [1, 2]),
            (('smth',), [3]),
            (('smth2',), ['a', 'b', 'c'])
        ])) == \
        {
            ('bu__dup-01', 'du'): [1],
            ('bu', 'du'): [2],
            ('smth',): [3],
            ('smth2__dup-02',): ['a'],
            ('smth2__dup-03',): ['b'],
            ('smth2',): ['c']
        }

