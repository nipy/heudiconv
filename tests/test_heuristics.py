from . import heudiconv

import os
from mock import patch
from six.moves import StringIO

from glob import glob
from os.path import join as pjoin, dirname
import csv
import re

import pytest

from datalad.api import Dataset


def test_smoke_converall(tmpdir):
    heudiconv.main(
        ("-f heuristics/convertall.py -c dcm2niix -o %s -b --datalad "
         "-s fmap_acq-3mm -d tests/data/{subject}/*" % tmpdir).split(' ')
    )


@pytest.mark.parametrize('heuristic', [ 'dbic_bids', 'convertall' ])
@pytest.mark.parametrize(
    'invocation', [
        "tests/data",    # our new way with automated groupping
        "-d tests/data/{subject}/* -s 01-fmap_acq-3mm" # "old" way specifying subject
        # should produce the same results
    ])
def test_dbic_bids_largely_smoke(tmpdir, heuristic, invocation):
    is_bids = True if heuristic == 'dbic_bids' else False
    arg = "-f heuristics/%s.py -c dcm2niix -o %s" % (heuristic, tmpdir)
    if is_bids:
        arg += " -b"
    arg += " --datalad "
    args = (
        arg + invocation
    ).split(' ')
    if heuristic != 'dbic_bids' and invocation == 'tests/data':
        # none other heuristic has mighty infotoids atm
        with pytest.raises(NotImplementedError):
            heudiconv.main(args)
        return
    heudiconv.main(args)
    ds = Dataset(str(tmpdir))
    assert ds.is_installed()
    assert not ds.repo.dirty
    head = ds.repo.get_hexsha()

    # and if we rerun -- should fail
    if heuristic != 'dbic_bids' and invocation != 'tests/data':
        # those guys -- they just plow through it ATM without failing, i.e.
        # the logic is to reprocess
        heudiconv.main(args)
    else:
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


@pytest.mark.parametrize(
    'invocation', [
        "tests/data",    # our new way with automated groupping
    ])
def test_scans_keys_dbic_bids(tmpdir, invocation):
    args = "-f heuristics/dbic_bids.py -c dcm2niix -o %s -b " % tmpdir
    args += invocation
    heudiconv.main(args.split())
    # for now check it exists
    scans_keys = glob(pjoin(tmpdir.strpath, '*/*/*/*/*.tsv'))
    assert(len(scans_keys) == 1)
    with open(scans_keys[0]) as f:
        reader = csv.reader(f, delimiter='\t')
        for i, row in enumerate(reader):
            if i == 0:
                assert(row == ['filename', 'acq_time', 'operator', 'randstr'])
            assert(len(row) == 4)
            if i != 0:
                assert(os.path.exists(pjoin(dirname(scans_keys[0]), row[0])))
                assert(re.match(
                    '^[\d]{4}-[\d]{2}-[\d]{2}T[\d]{2}:[\d]{2}:[\d]{2}$',
                    row[1]))


@patch('sys.stdout', new_callable=StringIO)
def test_ls(stdout):
    args = "-f heuristics/dbic_bids.py --command ls tests/data".split(' ')
    heudiconv.main(args)
    out = stdout.getvalue()
    assert 'StudySessionInfo(locator=' in out
    assert 'Halchenko/Yarik/950_bids_test4' in out