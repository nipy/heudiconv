import os
import os.path as op
from heudiconv.utils import (
    get_known_heuristics_with_descriptions,
    get_heuristic_description,
    load_heuristic
)

import pytest
from .utils import HEURISTICS_PATH


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


def test_load_heuristic():
    by_name = load_heuristic('reproin')
    from_file = load_heuristic(op.join(HEURISTICS_PATH, 'reproin.py'))

    assert by_name
    assert by_name.filename == from_file.filename

    with pytest.raises(ImportError):
        load_heuristic('unknownsomething')

    with pytest.raises(ImportError):
        load_heuristic(op.join(HEURISTICS_PATH, 'unknownsomething.py'))