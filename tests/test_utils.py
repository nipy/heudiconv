import os
from heudiconv.utils import (
    get_known_heuristics_with_descriptions,
    get_heuristic_description
)


def test_get_known_heuristics_with_descriptions():
    d = get_known_heuristics_with_descriptions()
    assert {'reproin', 'convertall'}.issubset(d)
    # ATM we include all, not only those two
    assert len(d) > 2
    assert len(d['reproin']) > 50  # it has a good one
    assert len(d['reproin'].split(os.sep)) == 1  # but just one line


def test_get_heuristic_description():
    desc = get_heuristic_description('reproin', full=True)
    assert len(desc) > 1000
    # and we describe such details as
    assert '_ses-' in desc
    assert '_run-' in desc
    # and mention ReproNim ;)
    assert 'ReproNim' in desc