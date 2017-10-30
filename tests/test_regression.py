"""Testing conversion with conversion saved on datalad"""
from tempfile import mkdtemp
import os
import os.path as op
import json
from glob import glob

import pytest

have_datalad = True
try:
	from datalad import api # to pull and grab data
except ImportError:
	have_datalad = False

from heudiconv.cli.run import main as runner
import heudiconv


def gen_heudiconv_args(datadir, outdir, subject, heuristic_file, xargs=None):
	heuristic = op.realpath(op.join(
								op.dirname(heudiconv.__file__),
					        	'..',
			        			'heuristics',
			        			heuristic_file))

	args = ["-d", op.join(datadir, 'sourcedata/{subject}/*/*/*.tgz'),
			"-c", "dcm2niix",
			"-o", outdir,
			"-s", subject,
			"-f", heuristic,
			"--bids",
			]
	if xargs:
		args += xargs

	return args

def fetch_data(tmpdir, subject):
	"""Fetches some test dicoms"""
	targetdir = os.path.join(tmpdir, 'QA')
	api.install(path=targetdir,
				source='///dbic/QA')
	api.get('{}/sourcedata/{}'.format(targetdir, subject))
	return targetdir

@pytest.mark.parametrize('subject', ['sub-sid000143'])
@pytest.mark.parametrize('heuristic', ['dbic_bids.py'])
@pytest.mark.skipif(not have_datalad, reason="no datalad")
def test_conversion(tmpdir, subject, heuristic):
	tmpdir.chdir()
	datadir = fetch_data(tmpdir.strpath, subject)
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
