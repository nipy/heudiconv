from heudiconv.cli.run import main as runner

import os
from mock import patch
from six.moves import StringIO

from glob import glob
from os.path import join as pjoin, dirname
import csv
import re

import pytest
from .utils import HEURISTICS_PATH, TESTS_DATA_PATH

import logging
lgr = logging.getLogger(__name__)

try:
    from datalad.api import Dataset
except ImportError:  # pragma: no cover
    Dataset = None


# this will fail if not in project's root directory
def test_smoke_converall(tmpdir):
    runner(
        ("-f %s/convertall.py -c dcm2niix -o %s -b --datalad "
         "-s fmap_acq-3mm -d %s/{subject}/*"
         % (HEURISTICS_PATH, tmpdir, TESTS_DATA_PATH)
        ).split(' ')
    )


@pytest.mark.parametrize('heuristic', ['dbic_bids', 'convertall'])
@pytest.mark.parametrize(
    'invocation', [
        "--files %s" % TESTS_DATA_PATH,    # our new way with automated groupping
        "-d %s/{subject}/* -s 01-fmap_acq-3mm" % TESTS_DATA_PATH # "old" way specifying subject
        # should produce the same results
    ])
@pytest.mark.skipif(Dataset is None, reason="no datalad")
def test_dbic_bids_largely_smoke(tmpdir, heuristic, invocation):
    is_bids = True if heuristic == 'dbic_bids' else False
    arg = "--random-seed 1 -f %s/%s.py -c dcm2niix -o %s" \
          % (HEURISTICS_PATH, heuristic, tmpdir)
    if is_bids:
        arg += " -b"
    arg += " --datalad "
    args = (
        arg + invocation
    ).split(' ')

    # Test some safeguards
    if invocation == "--files %s" % TESTS_DATA_PATH:
        # Multiple subjects must not be specified -- only a single one could
        # be overridden from the command line
        with pytest.raises(ValueError):
            runner(args + ['--subjects', 'sub1', 'sub2'])

        if heuristic != 'dbic_bids':
            # none other heuristic has mighty infotoids atm
            with pytest.raises(NotImplementedError):
                runner(args)
            return
    runner(args)
    ds = Dataset(str(tmpdir))
    assert ds.is_installed()
    assert not ds.repo.dirty
    head = ds.repo.get_hexsha()

    # and if we rerun -- should fail
    lgr.info(
        "RERUNNING, expecting to FAIL since the same everything "
        "and -c specified so we did conversion already"
    )
    with pytest.raises(RuntimeError):
        runner(args)

    # but there should be nothing new
    assert not ds.repo.dirty
    assert head == ds.repo.get_hexsha()

    # unless we pass 'overwrite' flag
    runner(args + ['--overwrite'])
    # but result should be exactly the same, so it still should be clean
    # and at the same commit
    assert ds.is_installed()
    assert not ds.repo.dirty
    assert head == ds.repo.get_hexsha()


@pytest.mark.parametrize(
    'invocation', [
        "--files %s/data" % TESTS_DATA_PATH,    # our new way with automated groupping
    ])
def test_scans_keys_dbic_bids(tmpdir, invocation):
    args = "-f %s/dbic_bids.py -c dcm2niix -o %s -b " % (HEURISTICS_PATH, tmpdir)
    args += invocation
    runner(args.split())
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
    args = (
            "-f %s/dbic_bids.py --command ls --files %s"
            % (HEURISTICS_PATH, TESTS_DATA_PATH)
    ).split(' ')
    runner(args)
    out = stdout.getvalue()
    assert 'StudySessionInfo(locator=' in out
    assert 'Halchenko/Yarik/950_bids_test4' in out
