from . import heudiconv

import os
from mock import patch
from six.moves import StringIO

import pytest

from datalad.api import Dataset


def test_smoke_converall(tmpdir):
    heudiconv.main(
        ("-f heuristics/convertall.py -c dcm2niix -o %s -b --datalad "
         "-s fmap_acq-3mm -d tests/data/%%s/*" % tmpdir).split(' ')
    )


def test_dbic_bids_largely_smoke(tmpdir):
    args = ("-f heuristics/dbic_bids.py -c dcm2niix -o %s -b "
            "--datalad tests/data" % tmpdir).split(' ');
    heudiconv.main(args)
    ds = Dataset(str(tmpdir))
    assert ds.is_installed()
    assert not ds.repo.dirty
    head = ds.repo.get_hexsha()

    # and if we rerun -- should fail
    with pytest.raises(RuntimeError):
        heudiconv.main(args)
    # but there should be nothing new
    assert not ds.repo.dirty
    assert head == ds.repo.get_hexsha()

    # unless we pass 'overwrite' flag
    heudiconv.main(args + ['--overwrite'])
    # but result should be exactly the same, so it still should be clean
    # and at the same commit
    assert ds.is_installed()
    assert not ds.repo.dirty
    assert head == ds.repo.get_hexsha()


@patch('sys.stdout', new_callable=StringIO)
def test_ls(stdout):
    args = "-f heuristics/dbic_bids.py --command ls tests/data".split(' ')
    heudiconv.main(args)
    out = stdout.getvalue()
    assert 'StudySessionInfo(locator=' in out
    assert 'Halchenko/Yarik/950_bids_test4' in out