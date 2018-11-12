"""Testing conversion with conversion saved on datalad"""
import json
from glob import glob

import pytest

have_datalad = True
try:
    from datalad import api # to pull and grab data
    from datalad.support.exceptions import IncompleteResultsError
except ImportError:
    have_datalad = False

import heudiconv
from heudiconv.cli.run import main as runner
# testing utilities
from .utils import fetch_data, gen_heudiconv_args


@pytest.mark.parametrize('subject', ['sub-sid000143'])
@pytest.mark.parametrize('heuristic', ['reproin.py'])
@pytest.mark.skipif(not have_datalad, reason="no datalad")
def test_conversion(tmpdir, subject, heuristic):
    tmpdir.chdir()
    try:
        datadir = fetch_data(tmpdir.strpath, subject)
    except IncompleteResultsError as exc:
        pytest.skip("Failed to fetch test data: %s" % str(exc))
    outdir = tmpdir.mkdir('out').strpath

    args = gen_heudiconv_args(datadir, outdir, subject, heuristic)
    runner(args) # run conversion

    # verify functionals were converted
    assert glob('{}/{}/func/*'.format(outdir, subject)) == \
           glob('{}/{}/func/*'.format(datadir, subject))

    # compare some json metadata
    json_ = '{}/task-rest_acq-24mm64sl1000tr32te600dyn_bold.json'.format
    orig, conv = (json.load(open(json_(datadir))),
                  json.load(open(json_(outdir))))
    keys = ['EchoTime', 'MagneticFieldStrength', 'Manufacturer', 'SliceTiming']
    for key in keys:
        assert orig[key] == conv[key]
