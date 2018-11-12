from heudiconv.cli.run import main as runner

import os
import os.path as op
from mock import patch
from six.moves import StringIO

from glob import glob
from os.path import join as pjoin, dirname
import csv
import re

import pytest
from .utils import TESTS_DATA_PATH

import logging
lgr = logging.getLogger(__name__)

try:
    from datalad.api import Dataset
except ImportError:  # pragma: no cover
    Dataset = None


# this will fail if not in project's root directory
def test_smoke_convertall(tmpdir):
    args = ("-c dcm2niix -o %s -b --datalad "
     "-s fmap_acq-3mm -d %s/{subject}/*"
     % (tmpdir, TESTS_DATA_PATH)
    ).split(' ')

    # complain if no heurisitic
    with pytest.raises(RuntimeError):
        runner(args)

    args.extend(['-f', 'convertall'])
    runner(args)


@pytest.mark.parametrize('heuristic', ['reproin', 'convertall'])
@pytest.mark.parametrize(
    'invocation', [
        "--files %s" % TESTS_DATA_PATH,    # our new way with automated groupping
        "-d %s/{subject}/* -s 01-fmap_acq-3mm" % TESTS_DATA_PATH # "old" way specifying subject
        # should produce the same results
    ])
@pytest.mark.skipif(Dataset is None, reason="no datalad")
def test_reproin_largely_smoke(tmpdir, heuristic, invocation):
    is_bids = True if heuristic == 'reproin' else False
    arg = "--random-seed 1 -f %s -c dcm2niix -o %s" \
          % (heuristic, tmpdir)
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

        if heuristic != 'reproin':
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
        "--files %s" % TESTS_DATA_PATH,    # our new way with automated groupping
    ])
def test_scans_keys_reproin(tmpdir, invocation):
    args = "-f reproin -c dcm2niix -o %s -b " % (tmpdir)
    args += invocation
    runner(args.split())
    # for now check it exists
    scans_keys = glob(pjoin(tmpdir.strpath, '*/*/*/*/*/*.tsv'))
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
            "-f reproin --command ls --files %s"
            % (TESTS_DATA_PATH)
    ).split(' ')
    runner(args)
    out = stdout.getvalue()
    assert 'StudySessionInfo(locator=' in out
    assert 'Halchenko/Yarik/950_bids_test4' in out


def test_scout_conversion(tmpdir):
    tmppath = tmpdir.strpath
    args = (
        "-b -f reproin --files %s"
        % (TESTS_DATA_PATH)
    ).split(' ') + ['-o', tmppath]
    runner(args)

    assert not op.exists(pjoin(
        tmppath,
        'Halchenko/Yarik/950_bids_test4/sub-phantom1sid1/ses-localizer/anat'))

    assert op.exists(pjoin(
        tmppath,
        'Halchenko/Yarik/950_bids_test4/sourcedata/sub-phantom1sid1/'
        'ses-localizer/anat/sub-phantom1sid1_ses-localizer_scout.dicom.tgz'
    )
    )
