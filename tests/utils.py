import os.path as op
import heudiconv.heuristics

HEURISTICS_PATH = op.join(heudiconv.heuristics.__path__[0])
TESTS_DATA_PATH = op.join(op.dirname(__file__), 'data')


def gen_heudiconv_args(datadir, outdir, subject, heuristic_file, xargs=None):
    heuristic = op.realpath(op.join(HEURISTICS_PATH, heuristic_file))
    args = ["-d", op.join(datadir, 'sourcedata/{subject}/*/*/*.tgz'),
            "-c", "dcm2niix",
            "-o", outdir,
            "-s", subject,
            "-f", heuristic,
            "--bids",]
    if xargs:
        args += xargs

    return args


def fetch_data(tmpdir, subject):
    """Fetches some test dicoms using datalad"""
    from datalad import api
    targetdir = op.join(tmpdir, 'QA')
    api.install(path=targetdir, source='http://datasets-tests.datalad.org/dbic/QA')
    api.get('{}/sourcedata/{}'.format(targetdir, subject))
    return targetdir
