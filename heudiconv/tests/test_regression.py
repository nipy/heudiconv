"""Testing conversion with conversion saved on datalad"""
import json
from glob import glob
import os.path as op

import pytest

have_datalad = True
try:
    from datalad import api # to pull and grab data
    from datalad.support.exceptions import IncompleteResultsError
except ImportError:
    have_datalad = False

from heudiconv.cli.run import main as runner
from heudiconv.utils import load_json
# testing utilities
from .utils import fetch_data, gen_heudiconv_args


@pytest.mark.parametrize('subject', ['sub-sid000143'])
@pytest.mark.parametrize('heuristic', ['reproin.py'])
@pytest.mark.parametrize('anon_cmd', [None, 'anonymize_script.py'])
@pytest.mark.skipif(not have_datalad, reason="no datalad")
def test_conversion(tmpdir, subject, heuristic, anon_cmd):
    tmpdir.chdir()
    try:
        datadir = fetch_data(tmpdir.strpath,
                             "dbic/QA",  # path from datalad database root
                             getpath=op.join('sourcedata', subject))
    except IncompleteResultsError as exc:
        pytest.skip("Failed to fetch test data: %s" % str(exc))
    outdir = tmpdir.mkdir('out').strpath

    args = gen_heudiconv_args(datadir,
                              outdir,
                              subject,
                              heuristic,
                              anon_cmd,
                              template=op.join('sourcedata/{subject}/*/*/*.tgz'))
    runner(args) # run conversion

    # verify functionals were converted
    assert glob('{}/{}/func/*'.format(outdir, subject)) == \
           glob('{}/{}/func/*'.format(datadir, subject))

    # compare some json metadata
    json_ = '{}/task-rest_acq-24mm64sl1000tr32te600dyn_bold.json'.format
    orig, conv = (load_json(json_(datadir)),
                  load_json(json_(outdir)))
    keys = ['EchoTime', 'MagneticFieldStrength', 'Manufacturer', 'SliceTiming']
    for key in keys:
        assert orig[key] == conv[key]

@pytest.mark.skipif(not have_datalad, reason="no datalad")
def test_multiecho(tmpdir, subject='MEEPI', heuristic='bids_ME.py'):
    tmpdir.chdir()
    try:
        datadir = fetch_data(tmpdir.strpath, "dicoms/velasco/MEEPI")
    except IncompleteResultsError as exc:
        pytest.skip("Failed to fetch test data: %s" % str(exc))

    outdir = tmpdir.mkdir('out').strpath
    args = gen_heudiconv_args(datadir, outdir, subject, heuristic)
    runner(args) # run conversion

    # check if we have echo functionals
    echoes = glob(op.join('out', 'sub-' + subject, 'func', '*echo*nii.gz'))
    assert len(echoes) == 3

    # check EchoTime of each functional
    # ET1 < ET2 < ET3
    prev_echo = 0
    for echo in sorted(echoes):
        _json = echo.replace('.nii.gz', '.json')
        assert _json
        echotime = load_json(_json).get('EchoTime', None)
        assert echotime > prev_echo
        prev_echo = echotime

    events = glob(op.join('out', 'sub-' + subject, 'func', '*events.tsv'))
    for event in events:
        assert 'echo-' not in event
